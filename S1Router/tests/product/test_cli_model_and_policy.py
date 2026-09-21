"""R-002/R-010: thin CLI wrappers for policy validation and model install (ADR-018)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from s1router.cli import main
from s1router.domain.policy import default_policy

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def write_bundle(root: Path) -> Path:
    from test_local_model import write_bundle as _write_bundle

    return _write_bundle(root)


@pytest.mark.requirement("R-002")
def test_policy_validate_accepts_the_default_profile_and_reports_its_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(default_policy()))
    assert main(["policy", "validate", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["valid"] is True
    assert isinstance(result["policy_ref"], str) and len(result["policy_ref"]) == 64


@pytest.mark.requirement("R-002")
def test_policy_validate_rejects_an_invalid_profile_with_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(default_policy() | {"providers": []}))
    assert main(["policy", "validate", str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "invalid_configuration"


@pytest.mark.requirement("R-002")
def test_policy_validate_reports_unreadable_file_with_exit_four(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["policy", "validate", str(tmp_path / "absent.json")]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "input_unavailable"


@pytest.mark.requirement("R-002")
def test_policy_validate_rejects_malformed_json_with_exit_two_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "policy.json"
    path.write_text("{not valid json")
    assert main(["policy", "validate", str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "invalid_configuration"


@pytest.mark.requirement("R-010")
def test_model_install_activates_a_verified_bundle_and_reports_its_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = write_bundle(tmp_path / "source")
    root = tmp_path / "installed"
    assert main(["model", "install", str(source), "--root", str(root)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["installed"] is True
    assert result["root"] == str(root)
    from s1m.artifacts.bundle import verify

    assert verify(root / "active") == result["model_ref"]


@pytest.mark.requirement("R-010")
def test_model_install_rejects_a_corrupt_bundle_with_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text("not json")
    assert main(["model", "install", str(source), "--root", str(tmp_path / "installed")]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "artifact_corrupt"


@pytest.mark.requirement("R-010")
def test_model_install_reports_missing_source_with_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A source that does not exist fails the same integrity check as a corrupt one."""
    assert (
        main(["model", "install", str(tmp_path / "absent"), "--root", str(tmp_path / "installed")])
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "artifact_corrupt"


@pytest.mark.requirement("R-010")
def test_model_install_reports_unusable_root_with_exit_four(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = write_bundle(tmp_path / "source")
    occupied_root = tmp_path / "occupied"
    occupied_root.write_text("not a directory")
    assert main(["model", "install", str(source), "--root", str(occupied_root)]) == 4
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "input_unavailable"
