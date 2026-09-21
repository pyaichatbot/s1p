"""Calibration fitting that structurally cannot see non-calibration data (M-007).

s1m must not import s1router: the composition/adapter direction runs
router -> model (see ``packages/router/src/s1router/adapters/local.py`` and
``scripts/check_architecture.py``), never the reverse, or the two packages
would form an import cycle. ``fit`` therefore returns a plain
``CalibrationBinding`` value -- the identity/provenance and thresholds a
calibration was fit under -- rather than a
``s1router.domain.acceptance.CalibrationProfile``. A router-side composition
root turns the binding into a real ``CalibrationProfile`` with
``CalibrationProfile.create(binding.provenance, dataset_hash=binding.dataset_hash,
expires_at=binding.expires_at, probability=binding.probability, margin=binding.margin)``.
That downstream binding is what makes a later precision/weights/rubric/
preprocessor change invalidate calibration, because ``accept()`` compares a
prediction's full provenance tuple against the profile's bound identity and
returns ``calibration_mismatch`` on any difference. This module's job is the
other half of M-007: guaranteeing the *inputs* to that binding are honest,
by making it structurally impossible for a ``TRAIN``, ``VALIDATION`` or
``FINAL_TEST`` record to reach calibration fitting in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from s1m.data.split import SplitRole
from s1m.data.validation import Record


class CalibrationFitError(ValueError):
    """Raised when a non-calibration-role record reaches calibration fitting."""


@dataclass(frozen=True)
class CalibrationBinding:
    """The artifact identity and thresholds a calibration was fit under.

    A plain data value (not a ``CalibrationProfile``) so this package does
    not depend on ``s1router``; see the module docstring for why.
    """

    provenance: dict[str, Any]
    dataset_hash: str
    expires_at: float
    probability: float
    margin: float


def fit(
    records: list[Record],
    provenance: dict[str, Any],
    *,
    dataset_hash: str,
    expires_at: float,
    probability: float,
    margin: float,
) -> CalibrationBinding:
    """Fit a calibration binding from exclusively ``SplitRole.CALIBRATION`` records.

    Raises ``CalibrationFitError`` -- loudly, never by silently dropping the
    offending rows -- if any input record's ``split`` is not
    ``SplitRole.CALIBRATION``. This is the leakage boundary from
    ``s1m.data.split``: ``TRAIN`` and ``VALIDATION`` records were never
    reviewed against final ground truth, and ``FINAL_TEST`` records must
    never influence any fitted parameter, so none of the three may reach
    this function's fitting path.
    """
    if not records:
        raise CalibrationFitError("no calibration records supplied")
    offending = [record for record in records if record.split != SplitRole.CALIBRATION]
    if offending:
        roles = sorted({str(record.split) for record in offending})
        ids = sorted(record.example_id for record in offending)
        raise CalibrationFitError(
            f"records with non-calibration split role(s) {roles} cannot reach "
            f"calibration fitting: {ids}"
        )
    return CalibrationBinding(
        provenance=dict(provenance),
        dataset_hash=dataset_hash,
        expires_at=expires_at,
        probability=probability,
        margin=margin,
    )
