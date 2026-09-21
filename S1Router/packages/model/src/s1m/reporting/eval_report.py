"""M-008: evaluation report of errors, coverage, counts, CIs, slices, baseline.

Evaluation runs against an explicitly declared, single, uniform split role
(``FINAL_TEST`` or ``CALIBRATION`` from ``s1m.data.split``); an evaluation
set spanning multiple split roles, or run against ``TRAIN``/``VALIDATION``,
is rejected rather than silently mixed. A zero-example set, or a set with
zero accepted (non-abstained) predictions, raises rather than producing a
misleadingly-empty or trivially-perfect report ("zero accepts fails").

Wilson intervals are descriptive, not the exact one-sided release bound.
An optional frozen baseline prediction map is supplied by the caller; this
helper never learns a majority class from evaluation labels. Its provenance
still needs independent review. No baseline supplied means no comparison.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from s1m.data.split import SplitRole
from s1m.data.validation import Record

Status = Literal["predicted", "abstained"]

#: z for a two-sided 95% Wilson interval (Phi^-1(0.975)).
_Z95 = 1.959963984540054


class EvalReportError(ValueError):
    """Raised for empty inputs, zero accepts, or an ambiguous split role."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """One evaluated example: its ground-truth record and predicted status."""

    record: Record
    status: Status
    predicted_label: str | None

    def __post_init__(self) -> None:
        if self.status not in ("predicted", "abstained"):
            raise EvalReportError(f"status must be 'predicted' or 'abstained', got {self.status!r}")
        if self.status == "predicted" and not self.predicted_label:
            raise EvalReportError("a predicted outcome requires a non-empty predicted_label")
        if self.status == "abstained" and self.predicted_label is not None:
            raise EvalReportError("an abstained outcome must not set predicted_label")


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    lower: float
    upper: float


@dataclass(frozen=True, slots=True)
class SliceMetrics:
    key: str
    total: int
    accepted: int
    correct: int
    error_rate: float | None


@dataclass(frozen=True, slots=True)
class EvalReport:
    split: SplitRole
    total: int
    accepted: int
    coverage: float
    error_rate: float
    error_ci: WilsonInterval
    counts_by_label: dict[str, int]
    slices: tuple[SliceMetrics, ...]
    baseline_error_rate: float | None


def wilson_interval(successes: int, total: int, z: float = _Z95) -> WilsonInterval:
    """The two-sided Wilson score interval for ``successes`` out of ``total``."""
    if total <= 0:
        raise EvalReportError("wilson_interval requires a positive total")
    if not (0 <= successes <= total):
        raise EvalReportError("successes must be between 0 and total")
    p = successes / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return WilsonInterval(max(0.0, (center - margin) / denom), min(1.0, (center + margin) / denom))


def _declared_split(outcomes: tuple[Outcome, ...]) -> SplitRole:
    splits = {outcome.record.split for outcome in outcomes}
    if len(splits) != 1 or None in splits:
        raise EvalReportError("evaluation set must declare exactly one split role")
    (declared,) = splits
    assert declared is not None
    role = SplitRole(declared)
    if role not in (SplitRole.FINAL_TEST, SplitRole.CALIBRATION):
        raise EvalReportError(f"evaluation must run on final_test or calibration, got {role}")
    return role


def _require_ground_truth(accepted: list[Outcome]) -> None:
    if any(outcome.record.label is None for outcome in accepted):
        raise EvalReportError("every accepted example must have a ground-truth label")


def _slice_metrics(outcomes: tuple[Outcome, ...], field: str) -> tuple[SliceMetrics, ...]:
    keys = sorted({str(getattr(outcome.record, field)) for outcome in outcomes})
    result: list[SliceMetrics] = []
    for key in keys:
        group = [o for o in outcomes if str(getattr(o.record, field)) == key]
        accepted = [o for o in group if o.status == "predicted"]
        correct = sum(1 for o in accepted if o.predicted_label == o.record.label)
        rate = (len(accepted) - correct) / len(accepted) if accepted else None
        result.append(SliceMetrics(key, len(group), len(accepted), correct, rate))
    return tuple(result)


def build_eval_report(
    outcomes: list[Outcome],
    *,
    slice_field: str = "task_id",
    baseline_predictions: dict[str, str] | None = None,
) -> EvalReport:
    """Build an ``EvalReport`` from evaluated outcomes, or raise loudly.

    Raises ``EvalReportError`` for: an empty ``outcomes`` list; outcomes that
    do not all declare the same single ``FINAL_TEST``/``CALIBRATION`` split
    role; an accepted (``predicted``) outcome missing its ground-truth
    label; or zero accepted outcomes overall ("zero accepts fails").
    """
    if not outcomes:
        raise EvalReportError("zero examples: cannot evaluate an empty set")
    items = tuple(outcomes)
    ids = [item.record.example_id for item in items]
    if len(set(ids)) != len(ids):
        raise EvalReportError("duplicate evaluation example")
    if slice_field not in {"task_id", "language", "repository"}:
        raise EvalReportError("unsupported slice field")
    split = _declared_split(items)
    accepted = [outcome for outcome in items if outcome.status == "predicted"]
    if not accepted:
        raise EvalReportError("zero accepts: cannot report on a set with no accepted predictions")
    _require_ground_truth(accepted)
    baseline_error = None
    if baseline_predictions is not None:
        if set(baseline_predictions) != set(ids) or any(
            not isinstance(label, str) or not label for label in baseline_predictions.values()
        ):
            raise EvalReportError("baseline must provide frozen predictions for every example")
        baseline_error = sum(
            baseline_predictions[o.record.example_id] != o.record.label for o in accepted
        ) / len(accepted)
    correct = sum(1 for outcome in accepted if outcome.predicted_label == outcome.record.label)
    errors = len(accepted) - correct
    labels = (outcome.record.label for outcome in accepted)
    counts_by_label = {
        label: count for label, count in Counter(labels).items() if label is not None
    }
    return EvalReport(
        split=split,
        total=len(items),
        accepted=len(accepted),
        coverage=len(accepted) / len(items),
        error_rate=errors / len(accepted),
        error_ci=wilson_interval(errors, len(accepted)),
        counts_by_label=counts_by_label,
        slices=_slice_metrics(items, slice_field),
        baseline_error_rate=baseline_error,
    )
