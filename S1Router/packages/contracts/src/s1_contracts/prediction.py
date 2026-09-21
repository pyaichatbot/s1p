"""Strict canonical prediction admission; provider claims confer no trust."""

from __future__ import annotations

import copy
import math
import re
from typing import Any

from s1_contracts.request import ensure, identifier, object_fields, text

REASONS = frozenset(
    "unsupported_task unsupported_language input_too_long too_many_choices missing_calibration "
    "calibration_mismatch low_confidence low_margin rule_conflict remote_disabled data_policy "
    "budget_exhausted deadline_exceeded provider_unavailable invalid_provider_output "
    "mandatory_review audit_unavailable invalid_request invalid_configuration "
    "invalid_contract_version artifact_missing artifact_corrupt incompatible_runtime "
    "queue_full rate_limited cancelled inference_failed internal_error".split()
)
PROVENANCE_FIELDS = frozenset(
    "provider_id model_ref tokenizer_hash preprocessor_hash definition_hash precision "
    "runtime_version calibration_ref".split()
)
PREDICTION_FIELDS = set(
    "question_id status probabilities selected_id p_true expected_value confidence "
    "calibration_status provenance reason".split()
)


def finite(value: Any, low: float, high: float) -> bool:
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def validate_provenance(value: Any) -> dict[str, Any]:
    provenance = object_fields(value, set(PROVENANCE_FIELDS))
    identifier(provenance["provider_id"])
    for key in ("model_ref", "precision", "runtime_version"):
        text(provenance[key])
    for key in ("tokenizer_hash", "preprocessor_hash", "definition_hash"):
        ensure(isinstance(provenance[key], str))
        ensure(re.fullmatch(r"[a-f0-9]{64}", provenance[key]) is not None)
    if provenance["calibration_ref"] is not None:
        text(provenance["calibration_ref"])
    return provenance


def validate_prediction(value: Any, question: dict[str, Any]) -> dict[str, Any]:
    """Validate against an admitted question; return an independently owned value."""
    try:
        result = object_fields(value, PREDICTION_FIELDS)
        ensure(result["question_id"] == question["id"])
        ensure(result["status"] in ("predicted", "unsupported", "error"))
        ensure(result["calibration_status"] in ("raw", "calibrated", "unavailable"))
        provenance = validate_provenance(result["provenance"])
        ensure(
            provenance["definition_hash"] == question["definition_hash"]
            or (result["status"] == "unsupported" and result["reason"] == "unsupported_task")
        )
        reason = result["reason"]
        ensure(reason is None or (isinstance(reason, str) and reason in REASONS))
        if result["status"] != "predicted":
            ensure(reason is not None)
            ensure(result["calibration_status"] != "calibrated")
            ensure(
                all(
                    result[key] is None
                    for key in (
                        "probabilities",
                        "selected_id",
                        "p_true",
                        "expected_value",
                        "confidence",
                    )
                )
            )
            return copy.deepcopy(result)
        ensure(reason is None)
        if result["calibration_status"] == "calibrated":
            ensure(provenance["calibration_ref"] is not None)
        values = result["probabilities"]
        support = question["support"]
        ensure(isinstance(values, list) and len(values) == len(support))
        probabilities: list[float] = []
        for value, option in zip(values, support, strict=True):
            entry = object_fields(value, {"id", "probability"})
            ensure(entry["id"] == option["id"])
            ensure(finite(entry["probability"], 0, 1))
            probabilities.append(float(entry["probability"]))
        ensure(abs(math.fsum(probabilities) - 1) <= 1e-6)
        selected = max(range(len(probabilities)), key=probabilities.__getitem__)
        ensure(result["selected_id"] == support[selected]["id"])
        ensure(finite(result["confidence"], 0, 1))
        ensure(abs(result["confidence"] - probabilities[selected]) <= 1e-6)
        expected = (
            math.fsum(
                probability * option["value"]
                for probability, option in zip(probabilities, support, strict=True)
            )
            if question["kind"] == "score"
            else None
        )
        derived = {
            "p_true": probabilities[1] if question["kind"] == "bool" else None,
            "expected_value": expected,
        }
        for key, target in derived.items():
            if target is None:
                ensure(result[key] is None)
            else:
                ensure(
                    finite(
                        result[key], 0 if key == "p_true" else -1000, 1 if key == "p_true" else 1000
                    )
                )
                ensure(abs(result[key] - target) <= 1e-6)
        return copy.deepcopy(result)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise ValueError("invalid_provider_output") from exc
