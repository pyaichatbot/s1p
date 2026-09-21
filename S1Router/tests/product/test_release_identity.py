"""M-011: a changed-precision artifact cannot reuse release/acceptance status."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from s1m.artifacts.manifest import load
from s1m.artifacts.release_identity import check_release_identity

pytestmark = [pytest.mark.behavioral]


def write_bundle(root: Path, precision: str = "fp64") -> Path:
    root.mkdir()
    task = {
        "task_id": "sdlc.change_type",
        "task_version": 1,
        "kind": "choice",
        "instructions": "Classify the primary intended change.",
        "support": [
            {"id": "bug", "description": "Restore broken behavior"},
            {"id": "feature", "description": "Add behavior"},
        ],
        "state_schema": {"title": "string"},
        "languages": ["en"],
    }
    payloads = {
        "weights.json": {
            "format": "s1m.sparse-linear.v1",
            "labels": ["bug", "feature"],
            "bias": [0.0, 0.0],
            "features": {},
        },
        "tokenizer.json": {"type": "unicode-codepoint-v1"},
        "preprocessor.json": {"type": "unicode-word-count-v1", "fields": ["title"]},
    }
    for name, value in payloads.items():
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "LICENSE.txt").write_text("Synthetic test fixture; CC0-1.0", encoding="utf-8")
    manifest = {
        "format": "s1m.bundle.v1",
        "contract_version": "1.0",
        "precision": precision,
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


def manifest_hash(root: Path) -> str:
    return hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()


@pytest.mark.requirement("M-011")
def test_same_artifact_identity_reused_under_one_release_key_is_idempotent(
    tmp_path: Path,
) -> None:
    bundle = write_bundle(tmp_path / "bundle")
    reference, _, _ = load(bundle)

    check_release_identity(
        (
            (("sdlc.change_type", "1"), reference),
            (("sdlc.change_type", "1"), reference),
        )
    )


@pytest.mark.requirement("M-011")
def test_changed_precision_artifact_cannot_reuse_the_same_release_key(tmp_path: Path) -> None:
    original = write_bundle(tmp_path / "original", precision="fp64")
    original_reference, _, _ = load(original)

    changed = tmp_path / "changed-precision"
    changed.mkdir()
    for path in original.iterdir():
        (changed / path.name).write_bytes(path.read_bytes())
    manifest = json.loads((changed / "manifest.json").read_text())
    manifest["precision"] = "fp32"
    (changed / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    changed_reference = manifest_hash(changed)

    assert changed_reference != original_reference

    with pytest.raises(ValueError, match="invalid_configuration"):
        check_release_identity(
            (
                (("sdlc.change_type", "1"), original_reference),
                (("sdlc.change_type", "1"), changed_reference),
            )
        )


@pytest.mark.requirement("M-011")
def test_changed_precision_artifact_is_accepted_under_an_explicit_new_release_key(
    tmp_path: Path,
) -> None:
    original = write_bundle(tmp_path / "original", precision="fp64")
    original_reference, _, _ = load(original)

    changed = tmp_path / "changed-precision"
    changed.mkdir()
    for path in original.iterdir():
        (changed / path.name).write_bytes(path.read_bytes())
    manifest = json.loads((changed / "manifest.json").read_text())
    manifest["precision"] = "fp32"
    (changed / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    changed_reference = manifest_hash(changed)

    check_release_identity(
        (
            (("sdlc.change_type", "1"), original_reference),
            (("sdlc.change_type", "2"), changed_reference),
        )
    )


@pytest.mark.requirement("M-011")
def test_invalid_reference_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_configuration"):
        check_release_identity((("release", ""),))
