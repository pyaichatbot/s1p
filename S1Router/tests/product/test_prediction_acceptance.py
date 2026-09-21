"""R-001/R-004 trust boundary and exact-label acceptance scenarios."""

from __future__ import annotations

import copy
import importlib
from typing import Any

import pytest
from s1_contracts.request import example_request

pytestmark = [pytest.mark.behavioral, pytest.mark.contract]


def api(module: str) -> Any:
    try:
        return importlib.import_module(module)
    except ModuleNotFoundError:
        pytest.fail(f"Missing full-product behavior: {module}")


def example(kind: str = "choice") -> tuple[dict[str, Any], dict[str, Any]]:
    question = example_request()["questions"][0]
    if kind == "bool":
        question.update(
            kind="bool",
            support=[
                {"id": "false", "description": "False"},
                {"id": "true", "description": "True"},
            ],
        )
        values = [0.96, 0.04]
    elif kind == "score":
        question.update(
            kind="score",
            support=[{"id": str(i), "value": i, "rubric": str(i)} for i in [1, 2, 3, 4, 5]],
        )
        values = [0.05, 0.05, 0.1, 0.7, 0.1]
    else:
        values = [0.91, 0.03, 0.03, 0.03]
    selected = max(range(len(values)), key=values.__getitem__)
    provenance = {
        "provider_id": "local",
        "model_ref": "checkpoint@sha256",
        "tokenizer_hash": "a" * 64,
        "preprocessor_hash": "b" * 64,
        "definition_hash": question["definition_hash"],
        "precision": "fp32",
        "runtime_version": "cpu@1",
        "calibration_ref": "temperature@1",
    }
    prediction = {
        "question_id": question["id"],
        "status": "predicted",
        "probabilities": [
            {"id": option["id"], "probability": value}
            for option, value in zip(question["support"], values, strict=True)
        ],
        "selected_id": question["support"][selected]["id"],
        "confidence": values[selected],
        "p_true": values[1] if kind == "bool" else None,
        "expected_value": 3.75 if kind == "score" else None,
        "calibration_status": "calibrated",
        "provenance": provenance,
        "reason": None,
    }
    return question, prediction


@pytest.mark.requirement("R-001")
@pytest.mark.parametrize("kind", ["choice", "bool", "score"])
def test_canonical_predictions_and_owned_output(kind: str) -> None:
    module = api("s1_contracts.prediction")
    question, prediction = example(kind)
    validated = module.validate_prediction(prediction, question)
    assert validated == prediction
    prediction["probabilities"][0]["probability"] = 0
    assert validated["probabilities"][0]["probability"] != 0


@pytest.mark.requirement("R-001")
@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "missing",
        "order",
        "sum",
        "nan",
        "infinity",
        "bool",
        "huge",
        "selected",
        "derived",
        "provenance",
        "question",
        "reason",
        "calibration",
    ],
)
def test_untrusted_output_rejected(mutation: str) -> None:
    module = api("s1_contracts.prediction")
    question, prediction = example()
    if mutation == "unknown":
        prediction["secret"] = "raw input"
    elif mutation == "missing":
        prediction["probabilities"].pop()
    elif mutation == "order":
        prediction["probabilities"].reverse()
    elif mutation in {"nan", "infinity", "bool", "huge", "sum"}:
        prediction["probabilities"][0]["probability"] = {
            "nan": float("nan"),
            "infinity": float("inf"),
            "bool": True,
            "huge": 10**400,
            "sum": 0.5,
        }[mutation]
    elif mutation == "selected":
        prediction["selected_id"] = "feature"
    elif mutation == "derived":
        prediction["confidence"] = 0.1
    elif mutation == "provenance":
        prediction["provenance"]["definition_hash"] = "c" * 64
    elif mutation == "question":
        prediction["question_id"] = "different"
    elif mutation == "reason":
        prediction["reason"] = "vendor secret text"
    elif mutation == "calibration":
        prediction["calibration_status"] = []
    with pytest.raises(ValueError, match="^invalid_provider_output$"):
        module.validate_prediction(prediction, question)


@pytest.mark.requirement("R-004")
def test_trusted_calibration_identity_expiry_and_mandatory_review() -> None:
    module = api("s1router.domain.acceptance")
    question, prediction = example()
    identity = copy.deepcopy(prediction["provenance"])
    profile = module.CalibrationProfile.create(
        identity, dataset_hash="d" * 64, expires_at=200, probability=0.9, margin=0.1
    )
    assert module.accept(question, prediction, profile, now=100) is None
    identity["precision"] = "int4"
    assert module.accept(question, prediction, profile, now=100) is None
    for field in prediction["provenance"]:
        changed = copy.deepcopy(prediction)
        changed["provenance"][field] = "e" * 64
        assert module.accept(question, changed, profile, now=100) == "calibration_mismatch"
    assert module.accept(question, prediction, None, now=100) == "missing_calibration"
    assert module.accept(question, prediction, profile, now=200) == "missing_calibration"
    assert (
        module.accept(question, prediction, profile, now=100, mandatory_review=True)
        == "mandatory_review"
    )
    prediction["calibration_status"] = "raw"
    assert module.accept(question, prediction, profile, now=100) == "missing_calibration"


@pytest.mark.requirement("R-004")
def test_equal_threshold_bool_false_and_exact_score_bin() -> None:
    module = api("s1router.domain.acceptance")
    for kind, threshold, expected in [
        ("choice", 0.91, None),
        ("choice", 0.910001, "low_confidence"),
        ("choice", 0.90, None),
        ("bool", 0.9, None),
        ("score", 0.9, "low_confidence"),
    ]:
        question, prediction = example(kind)
        profile = module.CalibrationProfile.create(
            prediction["provenance"],
            dataset_hash="d" * 64,
            expires_at=200,
            probability=threshold,
            margin=0.1,
        )
        assert module.accept(question, prediction, profile, now=100) == expected
    question, prediction = example()
    profile = module.CalibrationProfile.create(
        prediction["provenance"], dataset_hash="d" * 64, expires_at=200, probability=0.9, margin=0.9
    )
    assert module.accept(question, prediction, profile, now=100) == "low_margin"


@pytest.mark.requirement("R-001")
def test_abstention_and_derived_quantity_validation() -> None:
    module = api("s1_contracts.prediction")
    question, prediction = example()
    for status in ["unsupported", "error"]:
        failure = copy.deepcopy(prediction)
        failure.update(status=status, reason="unsupported_task", calibration_status="unavailable")
        for key in ["probabilities", "selected_id", "p_true", "expected_value", "confidence"]:
            failure[key] = None
        assert module.validate_prediction(failure, question) == failure
        failure["confidence"] = 0.9
        with pytest.raises(ValueError):
            module.validate_prediction(failure, question)
    for kind, key in [("bool", "p_true"), ("score", "expected_value")]:
        question, prediction = example(kind)
        prediction[key] += 0.01
        with pytest.raises(ValueError):
            module.validate_prediction(prediction, question)
    question, prediction = example()
    prediction["p_true"] = 0
    with pytest.raises(ValueError):
        module.validate_prediction(prediction, question)
    prediction["p_true"] = None
    prediction["provenance"]["calibration_ref"] = None
    with pytest.raises(ValueError):
        module.validate_prediction(prediction, question)
    prediction["calibration_status"] = "raw"
    assert module.validate_prediction(prediction, question)["calibration_status"] == "raw"
    malformed: list[Any] = [None, [], {}, {"question_id": "x"}]
    for value in malformed:
        with pytest.raises(ValueError):
            module.validate_prediction(value, question)


@pytest.mark.requirement("R-004")
def test_invalid_profiles_fail_and_direct_construction_cannot_bypass() -> None:
    module = api("s1router.domain.acceptance")
    _, prediction = example()
    options = {"dataset_hash": "d" * 64, "expires_at": 200, "probability": 0.9, "margin": 0.1}
    for field, value in [
        ("dataset_hash", "bad"),
        ("dataset_hash", None),
        ("expires_at", float("nan")),
        ("expires_at", -1),
        ("probability", True),
        ("probability", 1.01),
        ("margin", -0.01),
    ]:
        with pytest.raises(ValueError, match="invalid_configuration"):
            module.CalibrationProfile.create(prediction["provenance"], **(options | {field: value}))
    identity = copy.deepcopy(prediction["provenance"])
    identity["calibration_ref"] = None
    with pytest.raises(ValueError):
        module.CalibrationProfile.create(identity, **options)
    with pytest.raises(ValueError):
        module.CalibrationProfile(
            tuple(sorted(prediction["provenance"].items())), "d" * 64, 200, -1, 0
        )


@pytest.mark.requirement("R-004")
def test_exact_margin_ties_and_unusable_predictions() -> None:
    module = api("s1router.domain.acceptance")
    question, prediction = example("bool")
    prediction["probabilities"][0]["probability"] = 0.7
    prediction["probabilities"][1]["probability"] = 0.3
    prediction.update(confidence=0.7, p_true=0.3)
    profile = module.CalibrationProfile.create(
        prediction["provenance"], dataset_hash="d" * 64, expires_at=200, probability=0.7, margin=0.4
    )
    assert module.accept(question, prediction, profile, now=100) is None
    assert module.accept(question, prediction, profile, now=float("nan")) == "missing_calibration"
    prediction["status"] = "unsupported"
    assert module.accept(question, prediction, profile, now=100) == "missing_calibration"
    prediction["status"] = "predicted"
    prediction["provenance"]["definition_hash"] = question["definition_hash"] = "a" * 64
    profile = module.CalibrationProfile.create(
        prediction["provenance"],
        dataset_hash="d" * 64,
        expires_at=200,
        probability=0.5,
        margin=0.01,
    )
    question["definition_hash"] = "b" * 64
    assert module.accept(question, prediction, profile, now=100) == "calibration_mismatch"
    question["definition_hash"] = "a" * 64
    for item in prediction["probabilities"]:
        item["probability"] = 0.5
    prediction.update(confidence=0.5, p_true=0.5)
    assert module.accept(question, prediction, profile, now=100) == "low_margin"
    validated = api("s1_contracts.prediction").validate_prediction(prediction, question)
    assert validated["selected_id"] == "false"


@pytest.mark.requirement("R-004")
def test_profile_identity_cannot_retain_mutable_containers() -> None:
    module = api("s1router.domain.acceptance")
    _, prediction = example()
    with pytest.raises(ValueError, match="invalid_configuration"):
        module.CalibrationProfile(list(prediction["provenance"].items()), "d" * 64, 200, 0.9, 0.1)


@pytest.mark.requirement("R-001")
def test_derived_probability_cannot_escape_unit_interval_within_tolerance() -> None:
    module = api("s1_contracts.prediction")
    question, prediction = example("bool")
    prediction["probabilities"][0]["probability"] = 1
    prediction["probabilities"][1]["probability"] = 0
    prediction.update(confidence=1, p_true=-0.0000001)
    with pytest.raises(ValueError):
        module.validate_prediction(prediction, question)
