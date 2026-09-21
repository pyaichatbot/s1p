"""Immutable trusted calibration identity and exact-label acceptance policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from s1_contracts.prediction import finite, validate_provenance


@dataclass(frozen=True)
class CalibrationProfile:
    identity: tuple[tuple[str, str | None], ...]
    dataset_hash: str
    expires_at: float
    probability: float
    margin: float

    def __post_init__(self) -> None:
        try:
            if type(self.identity) is not tuple or any(
                type(pair) is not tuple for pair in self.identity
            ):
                raise ValueError("mutable identity")
            identity = validate_provenance(dict(self.identity))
            if (
                tuple(sorted(identity.items())) != self.identity
                or identity["calibration_ref"] is None
            ):
                raise ValueError("invalid calibration identity")
            if not isinstance(self.dataset_hash, str) or not re.fullmatch(
                r"[a-f0-9]{64}", self.dataset_hash
            ):
                raise ValueError("invalid dataset hash")
            if not finite(self.expires_at, 0, 1e15):
                raise ValueError("invalid expiry")
            if not finite(self.probability, 0, 1) or not finite(self.margin, 0, 1):
                raise ValueError("invalid gate")
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_configuration") from exc

    @classmethod
    def create(
        cls,
        provenance: dict[str, Any],
        *,
        dataset_hash: str,
        expires_at: float,
        probability: float,
        margin: float,
    ) -> CalibrationProfile:
        try:
            identity = validate_provenance(provenance)
            return cls(
                tuple(sorted(identity.items())), dataset_hash, expires_at, probability, margin
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_configuration") from exc


def accept(
    question: dict[str, Any],
    prediction: dict[str, Any],
    profile: CalibrationProfile | None,
    *,
    now: float,
    mandatory_review: bool = False,
) -> str | None:
    """Gate an already validated prediction against an installed trusted profile.

    The composition root must load profiles only from verified artifacts. This
    pure gate cannot establish dataset rights, calibration fitting or release approval.
    """
    if mandatory_review:
        return "mandatory_review"
    if (
        profile is None
        or prediction["status"] != "predicted"
        or prediction["calibration_status"] != "calibrated"
        or not finite(now, 0, 1e15)
        or now >= profile.expires_at
    ):
        return "missing_calibration"
    if (
        tuple(sorted(prediction["provenance"].items())) != profile.identity
        or prediction["provenance"]["definition_hash"] != question["definition_hash"]
    ):
        return "calibration_mismatch"
    probabilities = sorted((v["probability"] for v in prediction["probabilities"]), reverse=True)
    if probabilities[0] < profile.probability:
        return "low_confidence"
    margin = Decimal(str(probabilities[0])) - Decimal(str(probabilities[1]))
    if margin < Decimal(str(profile.margin)):
        return "low_margin"
    return None
