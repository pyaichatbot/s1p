"""M-008: errors/coverage, counts, CIs, slices, baseline; zero accepts fails."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import pytest
import s1m.data.split as _split
import s1m.data.validation as _validation
import s1m.reporting.eval_report as _eval_report

EvalReportError = _eval_report.EvalReportError
Outcome = _eval_report.Outcome
build_eval_report = _eval_report.build_eval_report
wilson_interval = _eval_report.wilson_interval
SplitRole = _split.SplitRole
validate_rows = _validation.validate_rows

pytestmark = [pytest.mark.behavioral]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def record(number: int, *, task_id: str, label: str | None, split: str) -> Any:
    body = f"Body for issue {number}."
    row = {
        "example_id": f"ghpr:{number}",
        "group_id": f"repo:{number}",
        "source_uri": f"https://example.invalid/issues/{number}",
        "source_revision": "2026-09-21T00:00:00Z",
        "source_license": "CC-BY-4.0",
        "source_license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "source_license_digest": digest("CC-BY-4.0"),
        "source_digest": digest("fixture-export"),
        "collected_at": "2026-09-21T00:00:00Z",
        "task_id": task_id,
        "task_version": "1",
        "language": "en",
        "title": f"Issue {number}",
        "body": body,
        "label": label,
        "label_origin": "human_adjudicated",
        "reviewer_ids": ["a", "b"],
        "adjudication_status": "adjudicated",
        "content_hash": digest(f"Issue {number}\n{body}"),
        "repository": "example/repo",
        "issue_number": str(number),
        "source_label": "bug",
        "duplicate_cluster": None,
        "near_duplicate_cluster": None,
        "template_cluster": None,
        "split": None,
    }
    (built,) = validate_rows([row])
    return replace(built, split=split)


def fixture_outcomes() -> list[Any]:
    rec1 = record(1, task_id="A", label="bug", split=SplitRole.FINAL_TEST)
    rec2 = record(2, task_id="A", label="bug", split=SplitRole.FINAL_TEST)
    rec3 = record(3, task_id="B", label="bug", split=SplitRole.FINAL_TEST)
    rec4 = record(4, task_id="B", label="feature", split=SplitRole.FINAL_TEST)
    rec5 = record(5, task_id="B", label="feature", split=SplitRole.FINAL_TEST)
    return [
        Outcome(rec1, "predicted", "bug"),
        Outcome(rec2, "predicted", "bug"),
        Outcome(rec3, "predicted", "feature"),
        Outcome(rec4, "predicted", "feature"),
        Outcome(rec5, "abstained", None),
    ]


@pytest.mark.requirement("M-008")
def test_normal_predictions_produce_full_report() -> None:
    built = build_eval_report(fixture_outcomes())

    assert built.split == SplitRole.FINAL_TEST
    assert built.total == 5
    assert built.accepted == 4
    assert built.coverage == pytest.approx(0.8)
    assert built.error_rate == pytest.approx(0.25)
    assert built.counts_by_label == {"bug": 3, "feature": 1}
    assert built.baseline_error_rate is None

    slices = {item.key: item for item in built.slices}
    assert slices["A"].total == 2 and slices["A"].accepted == 2
    assert slices["A"].error_rate == pytest.approx(0.0)
    assert slices["B"].total == 3 and slices["B"].accepted == 2
    assert slices["B"].error_rate == pytest.approx(0.5)


@pytest.mark.requirement("M-008")
def test_wilson_confidence_interval_matches_hand_computed_bounds() -> None:
    built = build_eval_report(fixture_outcomes())

    assert built.error_ci.lower == pytest.approx(0.045585, abs=1e-4)
    assert built.error_ci.upper == pytest.approx(0.699323, abs=1e-4)
    assert built.error_ci.lower < built.error_rate < built.error_ci.upper


@pytest.mark.requirement("M-008")
def test_wilson_interval_rejects_non_positive_total() -> None:
    with pytest.raises(EvalReportError):
        wilson_interval(0, 0)


@pytest.mark.requirement("M-008")
def test_zero_examples_raises_rather_than_reporting_empty() -> None:
    with pytest.raises(EvalReportError, match="zero examples"):
        build_eval_report([])


@pytest.mark.requirement("M-008")
def test_zero_accepted_predictions_raises_rather_than_reporting_trivially() -> None:
    outcomes = [
        Outcome(record(1, task_id="A", label="bug", split=SplitRole.FINAL_TEST), "abstained", None),
        Outcome(
            record(2, task_id="A", label="feature", split=SplitRole.FINAL_TEST), "abstained", None
        ),
    ]

    with pytest.raises(EvalReportError, match="zero accepts"):
        build_eval_report(outcomes)


@pytest.mark.requirement("M-008")
def test_mixed_split_roles_are_rejected() -> None:
    rec1 = record(1, task_id="A", label="bug", split=SplitRole.FINAL_TEST)
    rec2 = record(2, task_id="A", label="bug", split=SplitRole.CALIBRATION)
    outcomes = [
        Outcome(rec1, "predicted", "bug"),
        Outcome(rec2, "predicted", "bug"),
    ]

    with pytest.raises(EvalReportError, match="single|one split"):
        build_eval_report(outcomes)


@pytest.mark.requirement("M-008")
def test_non_holdout_split_role_is_rejected() -> None:
    outcomes = [
        Outcome(record(1, task_id="A", label="bug", split=SplitRole.TRAIN), "predicted", "bug"),
    ]

    with pytest.raises(EvalReportError, match="final_test or calibration"):
        build_eval_report(outcomes)


@pytest.mark.requirement("M-008")
def test_accepted_outcome_missing_ground_truth_label_is_rejected() -> None:
    unlabeled = record(1, task_id="A", label=None, split=SplitRole.FINAL_TEST)

    with pytest.raises(EvalReportError, match="ground-truth"):
        build_eval_report([Outcome(unlabeled, "predicted", "bug")])


@pytest.mark.requirement("M-008")
@pytest.mark.requirement("R-013")
def test_baseline_is_computed_over_the_identical_held_out_cases_as_the_router() -> None:
    outcomes = fixture_outcomes()
    # Frozen predictions intentionally differ from the test-set majority.
    baseline = {o.record.example_id: "feature" for o in outcomes}
    built = build_eval_report(outcomes, baseline_predictions=baseline)
    assert built.accepted == 4
    assert built.error_rate == pytest.approx(0.25)
    assert built.baseline_error_rate == pytest.approx(0.75)
    with pytest.raises(EvalReportError, match="every example"):
        build_eval_report(outcomes, baseline_predictions={})


@pytest.mark.requirement("M-008")
def test_missing_independent_baseline_and_zero_accept_slice_are_unavailable() -> None:
    outcomes = fixture_outcomes()
    outcomes[-1] = replace(outcomes[-1], record=replace(outcomes[-1].record, task_id="C"))
    report = build_eval_report(outcomes)
    assert report.baseline_error_rate is None
    assert next(s for s in report.slices if s.key == "C").error_rate is None


@pytest.mark.requirement("M-008")
def test_duplicate_examples_cannot_inflate_evaluation_counts() -> None:
    outcomes = fixture_outcomes()
    with pytest.raises(EvalReportError, match="duplicate"):
        build_eval_report([*outcomes, outcomes[0]])


@pytest.mark.requirement("M-008")
@pytest.mark.parametrize(
    "status,label", [("unknown", "bug"), ("predicted", None), ("abstained", "bug")]
)
def test_invalid_prediction_status_and_label_combinations_are_rejected(
    status: Any, label: Any
) -> None:
    with pytest.raises(EvalReportError):
        Outcome(fixture_outcomes()[0].record, status, label)


@pytest.mark.requirement("M-008")
def test_invalid_interval_counts_and_unsupported_slice_fail_closed() -> None:
    with pytest.raises(EvalReportError):
        wilson_interval(2, 1)
    with pytest.raises(EvalReportError, match="slice"):
        build_eval_report(fixture_outcomes(), slice_field="body")
