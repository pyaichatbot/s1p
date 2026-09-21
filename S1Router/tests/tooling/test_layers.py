"""Refusal and acceptance paths for scoped gates and installed smoke tooling."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import local_smoke, run_layer_ci
from scripts.check_repo import check_test_report


def test_layer_manifest_and_gate_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert len(run_layer_ci.requirements("1")) == 6
    with pytest.raises(ValueError, match="Unknown layer"):
        run_layer_ci.requirements("2")
    assert run_layer_ci.main([]) == 1
    assert run_layer_ci.main(["2"]) == 1
    monkeypatch.setattr(run_layer_ci, "ROOT", tmp_path)
    assert run_layer_ci.main(["1"]) == 1
    manifest = tmp_path / "docs/layers/l1/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"requirements": ["L1-001"]}')
    assert run_layer_ci.main(["1"]) == 1


def test_layer_runner_pass_and_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_layer_ci, "requirements", lambda layer: {"L1-001"})
    monkeypatch.setattr(pytest, "main", lambda args, plugins: pytest.ExitCode.TESTS_FAILED)
    assert run_layer_ci.main(["1"]) == 1
    monkeypatch.setattr(pytest, "main", lambda args, plugins: pytest.ExitCode.OK)
    monkeypatch.setattr(run_layer_ci, "check_test_report", lambda *args: None)
    monkeypatch.setattr(run_layer_ci, "check_coverage", lambda *args, **kwargs: None)
    (tmp_path / "reports/l1-coverage.json").write_text("{}")
    assert run_layer_ci.main(["1"]) == 0


def test_scoped_report_does_not_accept_planned_or_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import check_repo

    registry: dict[str, Any] = {"L1-001": {"status": "planned", "tests": []}}
    monkeypatch.setattr(check_repo, "check_traceability", lambda *args, **kwargs: registry)
    for selected in [set(), {"L1-002"}, {"L1-001"}]:
        with pytest.raises(ValueError):
            check_test_report(tmp_path, {}, selected)
    registry["L1-001"] = {"status": "implemented", "tests": ["test"]}
    registry["R-001"] = {"status": "planned", "tests": []}
    report = {
        "test": {
            "outcome": "passed",
            "requirements": ["L1-001"],
            "markers": ["behavioral", "contract", "integration", "architecture"],
        }
    }
    check_test_report(tmp_path, report, {"L1-001"})


def test_smoke_dispatches_all_expected_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    codes = iter([0, 3, 0, 2, 0, 0])
    outputs = iter([json.dumps({"state": {}}), "{}", "{}", "{}", "{}", "{}"])

    def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert Path(kwargs["cwd"]).is_dir()
        return subprocess.CompletedProcess(args, next(codes), next(outputs), "")

    monkeypatch.setattr(subprocess, "run", run)
    assert local_smoke.main() == 0
