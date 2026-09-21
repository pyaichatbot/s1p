"""Offline numerical inference and verified experimental artifact behavior."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from s1_contracts.capabilities import RegisteredTask
from s1_contracts.prediction import validate_prediction
from s1_contracts.request import example_request, task_definition
from s1m.artifacts.bundle import install, rollback, verify
from s1m.inference.runtime import LocalRuntime

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def write_bundle(root: Path, kind: str = "choice", strength: float = 3.0) -> Path:
    root.mkdir()
    task = task_definition()
    if kind == "bool":
        task.update(
            kind=kind,
            support=[
                {"id": "false", "description": "False"},
                {"id": "true", "description": "True"},
            ],
        )
    elif kind == "score":
        task.update(
            kind=kind,
            support=[
                {"id": "low", "value": 1, "rubric": "Low"},
                {"id": "high", "value": 5, "rubric": "High"},
            ],
        )
    width = len(task["support"])
    payloads = {
        "weights.json": {
            "format": "s1m.sparse-linear.v1",
            "labels": [item["id"] for item in task["support"]],
            "bias": [0.0] * width,
            "features": {"fix": [strength] + [0.0] * (width - 1)},
        },
        "tokenizer.json": {"type": "unicode-codepoint-v1"},
        "preprocessor.json": {"type": "unicode-word-count-v1", "fields": ["title", "body"]},
    }
    for name, value in payloads.items():
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "LICENSE.txt").write_text("Synthetic test fixture; CC0-1.0", encoding="utf-8")
    manifest = {
        "format": "s1m.bundle.v1",
        "contract_version": "1.0",
        "precision": "fp64",
        "runtime": "python-stdlib-v1",
        "task": task,
        "status": "experimental_fixture",
        "files": {
            name: {
                "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                "size_bytes": (root / name).stat().st_size,
            }
            for name in (*payloads, "LICENSE.txt")
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return root


def request_for(root: Path) -> dict[str, Any]:
    task = json.loads((root / "manifest.json").read_text())["task"]
    question = {
        key: value for key, value in task.items() if key not in {"state_schema", "languages"}
    }
    question.update(id="q1", definition_hash=RegisteredTask.create(task).reference)
    return example_request() | {"questions": [question]}


@pytest.mark.requirement("M-005")
@pytest.mark.parametrize("kind", ["choice", "bool", "score"])
def test_sparse_logits_produce_real_typed_distributions(tmp_path: Path, kind: str) -> None:
    source = write_bundle(tmp_path / "source", kind)
    install(source, tmp_path / "installed")
    request = request_for(source)
    result = LocalRuntime(tmp_path / "installed").predict(request)[0]
    validate_prediction(result, request["questions"][0])
    assert result["calibration_status"] == "raw"
    assert result["probabilities"][0]["probability"] > 0.8
    assert result["provenance"]["precision"] == "fp64"
    if kind == "bool":
        assert result["p_true"] < 0.1
        assert result["confidence"] > 0.9
    elif kind == "score":
        assert 1 < result["expected_value"] < 2


@pytest.mark.requirement("M-006")
def test_full_rendering_and_unsupported_task_never_call_model(
    tmp_path: Path, monkeypatch: Any
) -> None:
    source = write_bundle(tmp_path / "source")
    install(source, tmp_path / "installed")
    runtime = LocalRuntime(tmp_path / "installed", max_head_tokens=3)

    def fail(*args: Any) -> None:
        raise AssertionError("must not run inference")

    monkeypatch.setattr(runtime.model, "probabilities", fail)
    request = request_for(source)
    assert runtime.predict(request)[0]["reason"] == "input_too_long"
    request["questions"][0]["instructions"] = "Changed rubric"
    assert runtime.predict(request)[0]["reason"] == "unsupported_task"


@pytest.mark.requirement("M-009")
@pytest.mark.requirement("M-010")
def test_invalid_upgrade_preserves_active_and_verified_rollback(tmp_path: Path) -> None:
    source = write_bundle(tmp_path / "source")
    destination = tmp_path / "installed"
    first = install(source, destination)
    assert verify(destination / "active") == first
    bad = write_bundle(tmp_path / "bad")
    (bad / "weights.json").write_text("tampered")
    with pytest.raises(ValueError):
        install(bad, destination)
    (source / "escape").symlink_to(tmp_path / "bad")
    with pytest.raises(ValueError):
        install(source, destination)
    assert verify(destination / "active") == first
    second = write_bundle(tmp_path / "second", strength=4)
    install(second, destination)
    (destination / "active" / "weights.json").write_text("corrupt")
    with pytest.raises(ValueError):
        verify(destination / "active")
    assert rollback(destination) == first
    assert verify(destination / "active") == first


@pytest.mark.requirement("M-007")
@pytest.mark.requirement("M-009")
@pytest.mark.parametrize("change", ["precision", "files", "traversal", "calibration", "nan"])
def test_malformed_manifest_never_activates(tmp_path: Path, change: str) -> None:
    source = write_bundle(tmp_path / "source")
    manifest = json.loads((source / "manifest.json").read_text())
    if change == "precision":
        manifest["precision"] = "fp32"
    elif change == "files":
        manifest["files"] = {}
    elif change == "traversal":
        manifest["files"]["../escape"] = "0" * 64
    elif change == "calibration":
        manifest["calibration"] = {"temperature": 2, "identity": "unverified"}
    else:
        weights = json.loads((source / "weights.json").read_text())
        weights["bias"][0] = float("nan")
        (source / "weights.json").write_text(json.dumps(weights))
        manifest["files"]["weights.json"] = {
            "sha256": hashlib.sha256((source / "weights.json").read_bytes()).hexdigest(),
            "size_bytes": (source / "weights.json").stat().st_size,
        }
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        install(source, tmp_path / "installed")
    assert not (tmp_path / "installed" / "active").exists()


@pytest.mark.requirement("M-010")
def test_missing_artifact_fails_offline(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact_missing"):
        LocalRuntime(tmp_path / "missing")


@pytest.mark.requirement("M-005")
def test_extreme_logits_remain_finite_and_ties_are_stable() -> None:
    import math

    from s1m.inference.linear import SparseLinear

    weights = {
        "format": "s1m.sparse-linear.v1",
        "labels": ["a", "b"],
        "bias": [1e6, -1e6],
        "features": {},
    }
    model = SparseLinear(weights, ["a", "b"])
    assert model.probabilities("anything") == [1.0, 0.0]
    weights["bias"] = [0, 0]
    model = SparseLinear(weights, ["a", "b"])
    assert model.probabilities("anything") == [0.5, 0.5]
    assert all(math.isfinite(value) for value in model.probabilities("anything"))


@pytest.mark.requirement("M-009")
@pytest.mark.parametrize(
    "change",
    ["duplicate", "array", "license", "tokenizer", "fields", "labels", "term", "vector", "symlink"],
)
def test_invalid_payloads_rejected_even_with_matching_hash(tmp_path: Path, change: str) -> None:
    source = write_bundle(tmp_path / "source")
    manifest = json.loads((source / "manifest.json").read_text())
    name = "weights.json"
    weights = json.loads((source / name).read_text())
    if change == "duplicate":
        content = '{"format":"x","format":"y"}'
    elif change == "array":
        content = "[]"
    elif change == "license":
        name, content = "LICENSE.txt", " "
    elif change == "tokenizer":
        name, content = "tokenizer.json", '{"type":"different"}'
    elif change == "fields":
        name, content = "preprocessor.json", '{"type":"unicode-word-count-v1","fields":["missing"]}'
    elif change == "labels":
        weights["labels"].reverse()
        content = json.dumps(weights)
    elif change == "term":
        weights["features"] = {"NOT LOWERCASE": [0, 0, 0, 0]}
        content = json.dumps(weights)
    elif change == "vector":
        weights["bias"] = [True, 0, 0, 0]
        content = json.dumps(weights)
    else:
        outside = tmp_path / "outside"
        outside.write_bytes((source / name).read_bytes())
        (source / name).unlink()
        (source / name).symlink_to(outside)
        content = outside.read_text()
    if change != "symlink":
        (source / name).write_text(content)
    manifest["files"][name] = {
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "size_bytes": len(content.encode()),
    }
    (source / "manifest.json").write_text(json.dumps(manifest))
    expected = "incompatible_runtime" if change == "tokenizer" else "artifact_corrupt"
    with pytest.raises(ValueError, match=expected):
        install(source, tmp_path / "installed")


@pytest.mark.requirement("M-009")
@pytest.mark.requirement("M-010")
def test_idempotent_install_and_redirected_release_directory_fail_closed(tmp_path: Path) -> None:
    source = write_bundle(tmp_path / "source")
    destination = tmp_path / "installed"
    reference = install(source, destination)
    assert install(source, destination) == reference
    (destination / "releases").rename(destination / "moved")
    (destination / "releases").symlink_to(destination / "moved")
    with pytest.raises(ValueError):
        install(source, destination)


@pytest.mark.requirement("M-009")
@pytest.mark.requirement("M-010")
@pytest.mark.parametrize("pointer", ["active", "previous"])
def test_pointer_must_resolve_to_a_verified_release_inside_root(
    tmp_path: Path, pointer: str
) -> None:
    source = write_bundle(tmp_path / "source")
    destination = tmp_path / "installed"
    install(source, destination)
    if pointer == "previous":
        install(write_bundle(tmp_path / "second", strength=4), destination)
    outside = tmp_path / "outside"
    write_bundle(outside)
    (destination / pointer).unlink()
    (destination / pointer).symlink_to(outside)
    with pytest.raises(ValueError, match="artifact_corrupt"):
        verify(destination / pointer)
    if pointer == "active":
        with pytest.raises(ValueError, match="artifact_corrupt"):
            LocalRuntime(destination)
    else:
        with pytest.raises(ValueError, match="artifact_corrupt"):
            rollback(destination)


@pytest.mark.requirement("M-009")
def test_incompatible_manifest_preserves_typed_runtime_error(tmp_path: Path) -> None:
    source = write_bundle(tmp_path / "source")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["runtime"] = "python-other-v1"
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="incompatible_runtime"):
        verify(source)


@pytest.mark.requirement("M-009")
def test_pointer_rejects_release_directory_symlink(tmp_path: Path) -> None:
    source = write_bundle(tmp_path / "source")
    destination = tmp_path / "installed"
    reference = install(source, destination)
    release = destination / "releases" / reference
    moved = destination / "moved-release"
    release.rename(moved)
    release.symlink_to(moved)
    with pytest.raises(ValueError, match="artifact_corrupt"):
        verify(destination / "active")


@pytest.mark.requirement("M-006")
def test_unsupported_task_reports_actual_artifact_identity(tmp_path: Path) -> None:
    source = write_bundle(tmp_path / "source")
    install(source, tmp_path / "installed")
    request = request_for(source)
    request["questions"][0]["definition_hash"] = "f" * 64
    result = LocalRuntime(tmp_path / "installed").predict(request)[0]
    assert result["status"] == "unsupported"
    assert result["provenance"]["definition_hash"] != "f" * 64
    assert result["probabilities"] is None
    validate_prediction(result, request["questions"][0])
