"""Snapshot integrity, activation and rollback acceptance."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def api() -> Any:
    try:
        return importlib.import_module("s1router.deployment")
    except ModuleNotFoundError:
        pytest.fail("Missing verified snapshot deployment")


@pytest.mark.requirement("L1-006")
def test_verified_activation_idempotence_and_rollback(tmp_path: Path) -> None:
    module = api()
    source = tmp_path / "source"
    source.mkdir()
    file = source / "runtime.py"
    file.write_text("VALUE = 1\n")
    destination = tmp_path / "install"
    first = module.deploy({"runtime.py": file}, destination)
    assert module.verify(destination / "active") == first
    file.write_text("VALUE = 2\n")
    second = module.deploy({"runtime.py": file}, destination)
    assert second != first
    assert module.deploy({"runtime.py": file}, destination) == second
    assert module.rollback(destination) == first
    assert module.verify(destination / "active") == first
    (destination / "releases" / second / "runtime.py").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        module.rollback(destination)
    assert module.verify(destination / "active") == first
    with pytest.raises(ValueError):
        module.deploy({"../escape.py": file}, destination)
    with pytest.raises(ValueError):
        module.deploy({}, destination)
    with pytest.raises(ValueError):
        module.verify(tmp_path)


@pytest.mark.requirement("L1-006")
def test_tampered_or_missing_release_never_activates(tmp_path: Path) -> None:
    module = api()
    source = tmp_path / "a.py"
    source.write_text("x = 1\n")
    destination = tmp_path / "install"
    release = module.deploy({"a.py": source}, destination)
    with pytest.raises(ValueError):
        module.rollback(destination)
    (destination / "releases" / release / "extra.py").write_text("bad")
    with pytest.raises(ValueError):
        module.deploy({"a.py": source}, destination)
    (destination / "releases" / release / "extra.py").unlink()
    actual = destination / "releases" / release / "a.py"
    actual.unlink()
    actual.symlink_to(source)
    with pytest.raises(ValueError):
        module.verify(destination / "active")


@pytest.mark.architecture
@pytest.mark.requirement("L1-002")
def test_domain_has_no_io_or_ml_imports() -> None:
    root = Path(__file__).resolve().parents[2] / "packages/router/src/s1router/domain"
    allowed = {
        "__future__",
        "typing",
        "collections",
        "math",
        "s1_contracts",
        "re",
        "dataclasses",
        "decimal",
        "hashlib",
        "json",
    }
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in allowed for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] in allowed


@pytest.mark.requirement("L1-006")
def test_rollback_recovers_corrupt_active(tmp_path: Path) -> None:
    module = api()
    file = tmp_path / "source.py"
    file.write_text("first")
    first = module.deploy({"a.py": file}, tmp_path / "install")
    file.write_text("second")
    module.deploy({"a.py": file}, tmp_path / "install")
    (tmp_path / "install/active/a.py").write_text("corrupt")
    assert module.rollback(tmp_path / "install") == first
    assert module.verify(tmp_path / "install/active") == first


@pytest.mark.requirement("L1-005")
@pytest.mark.requirement("L1-006")
def test_installed_launcher_and_operator_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import os
    import subprocess

    module = api()
    root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "install"
    assert module.main(["deploy", "--root", str(root), "--destination", str(destination)]) == 0
    assert module.main(["status", "--destination", str(destination)]) == 0
    assert module.main(["rollback", "--destination", str(destination)]) == 1
    assert '"verified"' in capsys.readouterr().out
    launcher = destination / "bin/s1"
    env = dict(os.environ, S1_HOME=str(tmp_path / "state"))
    env.pop("PYTHONPATH", None)
    for command in ("example", "doctor", "observe"):
        result = subprocess.run(
            [str(launcher), command],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    (destination / "active/router/s1router/cli.py").write_text("tampered")
    result = subprocess.run(
        [str(launcher), "doctor"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 4
    assert "release_integrity_failure" in result.stdout
