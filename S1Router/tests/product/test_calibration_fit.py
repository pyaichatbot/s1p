"""M-007: modified identity invalidates calibration; final-test cannot reach fit."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from typing import Any

import pytest
from s1_contracts.request import definition_hash, example_request
from s1m.calibration.fit import (
    CalibrationBinding,
    CalibrationFitError,
    apply_temperature,
    fit,
)
from s1m.data.split import SplitRole
from s1m.data.validation import Record, validate_rows

pytestmark = [pytest.mark.behavioral]

PROVENANCE = {
    "provider_id": "local",
    "model_ref": "checkpoint@sha256",
    "tokenizer_hash": "a" * 64,
    "preprocessor_hash": "b" * 64,
    "definition_hash": definition_hash(),
    "precision": "fp32",
    "runtime_version": "cpu@1",
    "calibration_ref": "temperature@1",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def row(number: int, **changes: object) -> dict[str, object]:
    body = f"Body for issue {number}."
    result: dict[str, object] = {
        "example_id": f"ghpr:{number}",
        "group_id": f"repo:{number}",
        "source_uri": f"https://example.invalid/issues/{number}",
        "source_revision": "2026-09-21T00:00:00Z",
        "source_license": "CC-BY-4.0",
        "source_license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "source_license_digest": digest("CC-BY-4.0"),
        "source_digest": digest("fixture-export"),
        "collected_at": "2026-09-21T00:00:00Z",
        "task_id": "sdlc.change_type",
        "task_version": "1",
        "language": "en",
        "title": f"Issue {number}",
        "body": body,
        "label": "bug",
        "label_origin": "human_adjudicated",
        "reviewer_ids": ["a"],
        "adjudication_status": "adjudicated",
        "content_hash": digest(f"Issue {number}\n{body}"),
        "repository": f"example/repo{number}",
        "issue_number": str(number),
        "source_label": "bug",
        "duplicate_cluster": None,
        "near_duplicate_cluster": None,
        "template_cluster": None,
        "split": None,
    }
    result.update(changes)
    return result


def records_with_role(role: SplitRole) -> list[Record]:
    rows = [row(number) for number in range(1, 4)]
    return [replace(record, split=role) for record in validate_rows(rows)]


def fit_calibration(records: list[Record]) -> CalibrationBinding:
    return fit(
        records, PROVENANCE, dataset_hash="d" * 64, expires_at=200, probability=0.9, margin=0.1
    )


@pytest.mark.requirement("M-007")
def test_final_test_role_record_raises_loudly_and_is_not_silently_dropped() -> None:
    records = records_with_role(SplitRole.CALIBRATION)
    records[1] = replace(records[1], split=SplitRole.FINAL_TEST)

    with pytest.raises(CalibrationFitError) as error:
        fit_calibration(records)

    assert records[1].example_id in str(error.value)
    assert "final_test" in str(error.value)


@pytest.mark.requirement("M-007")
@pytest.mark.parametrize("role", [SplitRole.TRAIN, SplitRole.VALIDATION])
def test_train_and_validation_role_records_also_cannot_reach_fit(role: SplitRole) -> None:
    records = records_with_role(SplitRole.CALIBRATION)
    records[0] = replace(records[0], split=role)

    with pytest.raises(CalibrationFitError) as error:
        fit_calibration(records)

    assert str(role) in str(error.value)


@pytest.mark.requirement("M-007")
def test_empty_record_set_is_rejected_rather_than_binding_vacuously() -> None:
    with pytest.raises(CalibrationFitError):
        fit_calibration([])


@pytest.mark.requirement("M-007")
def test_all_calibration_role_records_fit_and_the_binding_gates_predictions() -> None:
    records = records_with_role(SplitRole.CALIBRATION)

    binding = fit_calibration(records)

    assert isinstance(binding, CalibrationBinding)
    assert binding.provenance == PROVENANCE

    import s1router.domain.acceptance as acceptance

    profile = acceptance.CalibrationProfile.create(
        binding.provenance,
        dataset_hash=binding.dataset_hash,
        expires_at=binding.expires_at,
        probability=binding.probability,
        margin=binding.margin,
    )
    question = example_request()["questions"][0]
    prediction: dict[str, Any] = {
        "question_id": question["id"],
        "status": "predicted",
        "probabilities": [
            {"id": option["id"], "probability": value}
            for option, value in zip(question["support"], [0.95, 0.03, 0.01, 0.01], strict=True)
        ],
        "selected_id": question["support"][0]["id"],
        "confidence": 0.95,
        "p_true": None,
        "expected_value": None,
        "calibration_status": "calibrated",
        "provenance": PROVENANCE,
        "reason": None,
    }
    assert acceptance.accept(question, prediction, profile, now=100) is None

    for field in ("precision", "model_ref", "tokenizer_hash", "preprocessor_hash"):
        changed = copy.deepcopy(PROVENANCE)
        changed[field] = "e" * 64 if field != "precision" else "int4"
        stale_profile = acceptance.CalibrationProfile.create(
            changed,
            dataset_hash=binding.dataset_hash,
            expires_at=binding.expires_at,
            probability=binding.probability,
            margin=binding.margin,
        )
        assert (
            acceptance.accept(question, prediction, stale_profile, now=100)
            == "calibration_mismatch"
        )


@pytest.mark.requirement("M-007")
def test_calibration_fit_estimates_bounded_temperature_from_reviewed_logits() -> None:
    records = records_with_role(SplitRole.CALIBRATION)
    logits = ((8.0, 0.0, 0.0, 0.0), (0.0, 8.0, 0.0, 0.0), (0.0, 0.0, 8.0, 0.0))
    labels = (1, 1, 2)

    binding = fit_calibration_with_scores(records, logits, labels)

    assert binding.temperature is not None
    assert 0.05 <= binding.temperature <= 100.0
    assert binding.fitting_method == "temperature_scaling.v1"
    assert binding.nll_after is not None and binding.nll_before is not None
    assert binding.nll_after < binding.nll_before
    assert apply_temperature((8.0, 0.0, 0.0, 0.0), binding.temperature)[0] == pytest.approx(
        8.0 / binding.temperature
    )


def fit_calibration_with_scores(
    records: list[Record], logits: tuple[tuple[float, ...], ...], labels: tuple[int, ...]
) -> CalibrationBinding:
    return fit(
        records,
        PROVENANCE,
        dataset_hash="d" * 64,
        expires_at=200,
        probability=0.9,
        margin=0.1,
        logits=logits,
        labels=labels,
    )


@pytest.mark.requirement("M-007")
def test_temperature_fit_rejects_unreviewed_calibration_records() -> None:
    records = [replace(records_with_role(SplitRole.CALIBRATION)[0], label_origin="source_weak")]

    with pytest.raises(CalibrationFitError, match="reviewed"):
        fit_calibration_with_scores(records, ((2.0, 0.0, 0.0, 0.0),), (0,))
