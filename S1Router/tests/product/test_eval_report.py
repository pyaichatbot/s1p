"""M-008: errors/coverage, counts, CIs, slices, baseline; zero accepts fails."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import replace
from typing import Any

import pytest

_eval_report = pytest.importorskip(
    "s1m.reporting.eval_report", reason="M-008 reporting module not yet implemented"
)
_split = pytest.importorskip(
    "s1m.data.split", reason="M-002/M-003 split module not yet implemented"
)
_validation = pytest.importorskip(
    "s1m.data.validation", reason="M-002/M-003 validation module not yet implemented"
)
EvalReportError = _eval_report.EvalReportError
Outcome = _eval_report.Outcome
build_eval_report = _eval_report.build_eval_report
wilson_interval = _eval_report.wilson_interval
SplitRole = _split.SplitRole
validate_rows = _validation.validate_rows

pytestmark = [pytest.mark.behavioral]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def record(number: int, *, task_id: str, label: str | None, split: object) -> Any:
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
    assert built.baseline_error_rate == pytest.approx(0.25)

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
    """R-013 "same held-out cases across baselines": ``build_eval_report`` takes
    one ``outcomes`` list and derives both the router's own ``error_rate`` and
    the ``baseline_error_rate`` from the exact same ``accepted`` subset of it
    -- there is no separate baseline run, no separate case selection, and so
    no way for the two to silently drift onto different held-out cases.

    This is proven, not merely asserted, by independently recomputing the
    majority-class baseline from the *same* accepted records the report
    reports ``accepted``/``error_rate`` for, and checking they agree; and by
    showing that adding an extra abstained (non-held-out-for-scoring)
    example changes neither number, because it never enters either
    computation's shared input.
    """
    outcomes = fixture_outcomes()
    built = build_eval_report(outcomes)

    accepted_records = [o for o in outcomes if o.status == "predicted"]
    assert built.accepted == len(accepted_records)
    labels = [o.record.label for o in accepted_records]
    majority = Counter(labels).most_common(1)[0][1]
    independently_recomputed_baseline = (len(labels) - majority) / len(labels)
    assert built.baseline_error_rate == pytest.approx(independently_recomputed_baseline)

    extra_abstained = Outcome(
        record(99, task_id="A", label="feature", split=SplitRole.FINAL_TEST), "abstained", None
    )
    with_extra = build_eval_report([*outcomes, extra_abstained])
    assert with_extra.accepted == built.accepted
    assert with_extra.error_rate == pytest.approx(built.error_rate)
    assert with_extra.baseline_error_rate == pytest.approx(built.baseline_error_rate)
