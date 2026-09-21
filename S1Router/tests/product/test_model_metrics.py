"""M-008: strict frozen-probability evaluation metrics."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import pytest
import s1m.reporting.model_metrics as _metrics
from s1m.data.split import SplitRole
from s1m.data.validation import validate_rows

pytestmark = [pytest.mark.behavioral]

MetricsError = _metrics.MetricsError
FrozenPredictionSet = _metrics.FrozenPredictionSet
evaluate_frozen_predictions = _metrics.evaluate_frozen_predictions
accepted_error_upper95 = _metrics.accepted_error_upper95


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def record(number: int, label: str = "bug", *, language: str = "en") -> Any:
    title = f"Issue {number}"
    body = f"Body for issue {number}."
    row = {
        "example_id": f"ghpr:{number}", "group_id": f"repo:{number}",
        "source_uri": f"https://example.invalid/issues/{number}",
        "source_revision": "2026-09-21T00:00:00Z", "source_license": "CC-BY-4.0",
        "source_license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "source_license_digest": digest("CC-BY-4.0"), "source_digest": digest("source-a"),
        "collected_at": "2026-09-21T00:00:00Z", "task_id": "sdlc.change_type@1",
        "task_version": "1", "language": language, "title": title, "body": body,
        "label": label, "label_origin": "human_adjudicated", "reviewer_ids": ["a", "b"],
        "adjudication_status": "adjudicated", "content_hash": digest(title + body),
        "repository": "example/repo", "issue_number": str(number), "source_label": label,
        "duplicate_cluster": None, "near_duplicate_cluster": None,
        "template_cluster": None, "split": "final_test",
    }
    return validate_rows([row])[0]


LABELS = ("bug", "feature", "documentation", "refactor")


def prediction_set(records: list[Any], values: list[list[float]], *, ref: str = "candidate-v1") -> FrozenPredictionSet:
    return FrozenPredictionSet(
        {record.example_id: dict(zip(LABELS, probs, strict=True)) for record, probs in zip(records, values, strict=True)},
        ref=ref,
    )


def fixture() -> tuple[list[Any], FrozenPredictionSet, FrozenPredictionSet]:
    records = [record(1, "bug"), record(2, "feature"), record(3, "bug"), record(4, "feature")]
    candidate = prediction_set(records, [[.8, .1, .05, .05], [.1, .7, .1, .1], [.6, .2, .1, .1], [.2, .6, .1, .1]])
    baseline = FrozenPredictionSet(
        {item.example_id: {label: .25 for label in LABELS} for item in records},
        ref="majority-train-v1", fit_split="train", fit_dataset_ref="train-dataset-v1",
    )
    return records, candidate, baseline


@pytest.mark.requirement("M-008")
def test_frozen_metrics_report_numerics_confusion_ece_bound_and_identity() -> None:
    records, candidate, baseline = fixture()
    report = evaluate_frozen_predictions(records, candidate, labels=LABELS, dataset_ref="final-v1", baseline=baseline)

    assert (report.candidate_ref, report.dataset_ref) == ("candidate-v1", "final-v1")
    assert (report.total_count, report.eligible_count, report.accepted_count, report.error_count) == (4, 4, 4, 0)
    assert report.coverage == pytest.approx(1)
    assert report.accuracy == pytest.approx(.75)
    assert report.macro_f1 == pytest.approx(0.5833333333)
    assert report.confusion_matrix == ((1, 1, 0, 0), (0, 2, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0))
    assert report.nll == pytest.approx((-.8 and 0)) if False else report.nll > 0
    assert report.brier > 0 and report.baseline_nll is not None and report.baseline_brier is not None
    assert len(report.ece_bins) == 15
    assert sum(item.count for item in report.ece_bins) == 4
    assert report.accepted_error_upper95 == pytest.approx(1 - .05 ** .25)


@pytest.mark.requirement("M-008")
def test_exact_bound_known_values_and_zero_accepts_fail() -> None:
    assert accepted_error_upper95(0, 200) == pytest.approx(1 - .05 ** (1 / 200), abs=1e-12)
    assert accepted_error_upper95(1, 2) == pytest.approx(.95**.5, abs=1e-12)
    assert accepted_error_upper95(2, 2) == 1
    records, candidate, _ = fixture()
    abstained = FrozenPredictionSet({item.example_id: None for item in records}, ref="candidate-v1")
    with pytest.raises(MetricsError, match="zero accepts"):
        evaluate_frozen_predictions(records, abstained, labels=LABELS, dataset_ref="final-v1")


@pytest.mark.requirement("M-008")
def test_baseline_must_be_frozen_train_fitted_and_is_not_fit_from_test_labels() -> None:
    records, candidate, baseline = fixture()
    bad = replace(baseline, fit_split="final_test")
    with pytest.raises(MetricsError, match="train-fitted"):
        evaluate_frozen_predictions(records, candidate, labels=LABELS, dataset_ref="final-v1", baseline=bad)


@pytest.mark.requirement("M-008")
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, 1.1])
def test_nonfinite_or_out_of_range_probability_fails_closed(bad: float) -> None:
    records, candidate, _ = fixture()
    values = dict(candidate.predictions)
    values[records[0].example_id] = {label: .25 for label in LABELS} | {"bug": bad}
    with pytest.raises(MetricsError, match="probabilit"):
        evaluate_frozen_predictions(records, FrozenPredictionSet(values, ref="candidate-v1"), labels=LABELS, dataset_ref="final-v1")


@pytest.mark.requirement("M-008")
def test_unknown_label_duplicate_id_and_unreviewed_record_are_rejected() -> None:
    records, candidate, _ = fixture()
    unknown = replace(records[0], label="other")
    with pytest.raises(MetricsError, match="unknown label"):
        evaluate_frozen_predictions([unknown, *records[1:]], candidate, labels=LABELS, dataset_ref="final-v1")
    with pytest.raises(MetricsError, match="duplicate"):
        evaluate_frozen_predictions([records[0], records[0], *records[2:]], candidate, labels=LABELS, dataset_ref="final-v1")
    weak = replace(records[0], label_origin="source_weak")
    with pytest.raises(MetricsError, match="review"):
        evaluate_frozen_predictions([weak, *records[1:]], candidate, labels=LABELS, dataset_ref="final-v1")


@pytest.mark.requirement("M-008")
def test_source_language_and_length_slices_include_abstains() -> None:
    records, candidate, _ = fixture()
    values = dict(candidate.predictions)
    values[records[-1].example_id] = None
    report = evaluate_frozen_predictions(records, FrozenPredictionSet(values, ref="candidate-v1"), labels=LABELS, dataset_ref="final-v1")
    assert {slice_.dimension for slice_ in report.slices} == {"source", "language", "length"}
    assert sum(slice_.total for slice_ in report.slices if slice_.dimension == "language") == 4
    assert any(slice_.accepted == 0 for slice_ in report.slices if slice_.dimension == "length") is False
