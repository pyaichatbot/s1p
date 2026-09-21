"""M-011/M-012: bound state transitions, never inherited by a changed export."""

import json
from pathlib import Path
from typing import Any

import pytest
from test_local_model import write_bundle

pytestmark = [
    pytest.mark.behavioral,
    pytest.mark.requirement("M-011"),
    pytest.mark.requirement("M-012"),
]


def calibration(ref: str) -> dict[str, Any]:
    return {
        "artifact_ref": ref,
        "dataset_ref": "a" * 64,
        "temperature": 1.5,
        "split": "calibration",
        "review_status": "human_reviewed",
    }


def test_export_identity_and_immutable_evidence_control_lifecycle(tmp_path: Path) -> None:
    from s1m.artifacts.lifecycle import Candidate

    original = Candidate.register(write_bundle(tmp_path / "one"))
    evidence = calibration(original.artifact_ref)
    fitted = original.calibrate(evidence)
    evidence["temperature"] = 9.0
    assert json.loads(fitted.calibration_json)["temperature"] == 1.5
    assert original.state == "experimental"
    assert fitted.state == "calibrated"
    changed = Candidate.register(write_bundle(tmp_path / "two", strength=4.0))
    assert changed.artifact_ref != original.artifact_ref
    assert changed.state == "experimental"
    with pytest.raises(ValueError, match="identity"):
        changed.calibrate(calibration(original.artifact_ref))
    with pytest.raises(ValueError, match="transition"):
        original.evaluate({})
    retired = fitted.retire()
    with pytest.raises(ValueError, match="transition"):
        retired.calibrate(calibration(retired.artifact_ref))


def test_candidate_cannot_approve_without_reviewed_quality_and_hardware(tmp_path: Path) -> None:
    from s1m.artifacts.lifecycle import Candidate

    candidate = Candidate.register(write_bundle(tmp_path / "one"))
    with pytest.raises(ValueError, match="transition"):
        candidate.approve({}, {})
    fitted = candidate.calibrate(calibration(candidate.artifact_ref))
    report = {
        "artifact_ref": candidate.artifact_ref,
        "calibration_ref": fitted.calibration_ref,
        "dataset_ref": "b" * 64,
        "split": "final_test",
        "review_status": "human_reviewed",
        "quality": {
            "eligible_count": 400,
            "accepted_count": 0,
            "errors": 0,
            "ece": 0.01,
            "nll": 0.1,
            "brier": 0.1,
            "baseline_nll": 0.5,
            "baseline_brier": 0.5,
        },
    }
    evaluated = fitted.evaluate(report)
    assert evaluated.state == "evaluated"
    with pytest.raises(ValueError):
        evaluated.approve({}, {})
    assert evaluated.state == "evaluated"
