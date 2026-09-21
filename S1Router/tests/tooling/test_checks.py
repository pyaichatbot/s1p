"""Behavioral checks for the local gate's refusal and acceptance paths."""

from __future__ import annotations

import copy
import importlib.metadata
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import check_repo as gate
from scripts import run_product_ci as runner


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name in gate.REQUIRED_DOCS + [
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "Makefile",
        "docs/traceability.json",
        "docs/layers/l1/manifest.json",
        "docs/layers/l1/evidence/verification.json",
        "docs/layers/l1/evidence/quality-verification.json",
        "docs/layers/l1/evidence/observation.json",
        "docs/layers/l1/evidence/maintenance.json",
    ]:
        source = gate.ROOT / name
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for name in (".codex", ".agents"):
        shutil.copytree(gate.ROOT / name, tmp_path / name)
    for name in ("packages", "tests/product"):
        shutil.copytree(gate.ROOT / name, tmp_path / name)
    gate.refresh_baseline(tmp_path, "Tooling fixture baseline, not production approval")
    return tmp_path


@pytest.fixture
def implemented(repo: Path) -> Path:
    data = gate.read_json(repo / "docs/traceability.json")
    for rid, entry in data.items():
        name = rid.lower().replace("-", "_")
        code = f"packages/router/src/s1router/{name}.py"
        test = f"tests/product/test_{name}.py"
        for path in (code, test):
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Fixture only; never release evidence\n")
        entry.update(status="implemented", code=[code], tests=[f"{test}::test_behavior"])
    write_json(repo / "docs/traceability.json", data)
    return repo


def passing_test_report(root: Path) -> dict[str, Any]:
    registry = gate.read_json(root / "docs/traceability.json")
    return {
        entry["tests"][0]: {
            "outcome": "passed",
            "requirements": [rid],
            "markers": ["behavioral", "contract", "architecture", "integration"],
        }
        for rid, entry in registry.items()
    }


def coverage_report(lines: int = 100, branches: int = 100) -> dict[str, Any]:
    summary = {
        "num_statements": 100,
        "covered_lines": lines,
        "num_branches": 100,
        "covered_branches": branches,
    }
    return {
        "totals": copy.deepcopy(summary),
        "files": {"packages/router/src/s1router/domain/core.py": {"summary": summary}},
    }


def release_report(root: Path) -> dict[str, Any]:
    artifact = root / "reports/evidence.json"
    write_json(artifact, {"notice": "TEST FIXTURE ONLY"})
    data = {
        "status": "candidate",
        "reviewer": "fixture-reviewer",
        "owner_decision_ref": "fixture-decision",
        "revision": "fixture-revision",
        "source_digest": gate.source_digest(root),
        "evidence": [
            {"purpose": purpose, "path": "reports/evidence.json", "sha256": gate.digest(artifact)}
            for purpose in gate.EVIDENCE_PURPOSES
        ],
        "quality": {
            "accepted_count": 300,
            "errors": 2,
            "eligible_count": 1000,
            "ece": 0.03,
            "nll": 0.4,
            "brier": 0.2,
            "baseline_nll": 0.7,
            "baseline_brier": 0.5,
        },
        "resources": {
            "bundle_bytes": 800_000_000,
            "peak_rss_bytes": 3_000_000_000,
            "warm_p95_ms": 300,
            "cold_p95_ms": 9000,
            "router_p95_ms": 5,
        },
    }
    write_json(root / "reports/release.json", data)
    return data


def test_foundation_is_not_product_readiness(repo: Path) -> None:
    gate.foundation(repo)
    with pytest.raises(ValueError, match="not implemented"):
        gate.check_traceability(repo, product=True)


def test_toolchain_rejects_environment_drift(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.0.0")
    with pytest.raises(ValueError, match="Installed version mismatch"):
        gate.check_toolchain(repo)


@pytest.mark.parametrize("replacement", ["pytest==0.0.0", "pytest>=9.1.1"])
def test_toolchain_rejects_unlocked_or_floating_dependencies(repo: Path, replacement: str) -> None:
    path = repo / "pyproject.toml"
    path.write_text(path.read_text().replace("pytest==9.1.1", replacement))
    with pytest.raises(ValueError):
        gate.check_toolchain(repo)


def test_spec_drift_requires_explicit_refresh(repo: Path) -> None:
    path = repo / "docs/s1router/spec.md"
    path.write_text(path.read_text() + "\nA changed requirement.\n")
    with pytest.raises(ValueError, match="Baseline drift"):
        gate.check_baseline(repo)
    with pytest.raises(ValueError, match="meaningful"):
        gate.refresh_baseline(repo, "")
    gate.refresh_baseline(repo, "Reviewed fixture specification change")
    gate.check_baseline(repo)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("missing", "Missing file"),
        ("link", "Broken local link"),
        ("source", "Missing source"),
        ("heading", "Missing heading"),
        ("placeholder", "Unresolved placeholder"),
        ("whitespace", "Trailing whitespace"),
    ],
)
def test_invalid_documents_fail(repo: Path, change: str, message: str) -> None:
    path = repo / "docs/s1router/intent.md"
    body = path.read_text()
    if change == "missing":
        path.unlink()
    else:
        edits = {
            "link": body + "\n[broken](missing.md)\n",
            "source": "# Document without a source\n",
            "heading": "Invalid heading\n[Source](https://example.org)\n",
            "placeholder": body + "\nTODO\n",
            "whitespace": body + "\ntrailing \n",
        }
        path.write_text(edits[change])
    with pytest.raises(ValueError, match=message):
        gate.check_docs(repo)


def test_anchor_and_fenced_examples_do_not_make_fake_links(repo: Path) -> None:
    path = repo / "docs/s1router/intent.md"
    path.write_text(
        path.read_text()
        + "\n[local](#purpose)\n"
        + chr(96) * 3
        + "\n[example](not-a-file)\n"
        + chr(96) * 3
        + "\n"
    )
    gate.check_docs(repo)


def test_paths_cannot_escape(repo: Path) -> None:
    with pytest.raises(ValueError, match="escapes"):
        gate.local_file(repo, "../outside.json")
    with pytest.raises(ValueError, match="Missing"):
        gate.local_file(repo, "absent.json")


@pytest.mark.parametrize(
    "mode", ["missing_agent", "agent_name", "agent_field", "skill", "skill_name"]
)
def test_invalid_agent_metadata_fails(repo: Path, mode: str) -> None:
    agent = repo / ".codex/agents/s1-architect.toml"
    skill = repo / ".agents/skills/s1-spec-change/SKILL.md"
    if mode == "missing_agent":
        agent.unlink()
    elif mode == "agent_name":
        agent.write_text(agent.read_text().replace('name = "s1-architect"', 'name = "other"'))
    elif mode == "agent_field":
        agent.write_text('name = "s1-architect"\n')
    elif mode == "skill":
        skill.write_text("# Missing metadata\n")
    else:
        skill.write_text(skill.read_text().replace("name: s1-spec-change", "name: other"))
    with pytest.raises(ValueError):
        gate.check_agents(repo)


@pytest.mark.parametrize("mode", ["missing_id", "invalid_status", "empty_acceptance", "duplicate"])
def test_registry_cannot_drift(repo: Path, mode: str) -> None:
    path = repo / "docs/traceability.json"
    data = gate.read_json(path)
    if mode == "missing_id":
        data.pop("R-001")
    elif mode == "invalid_status":
        data["R-001"]["status"] = "approved"
    elif mode == "empty_acceptance":
        data["R-001"]["acceptance"] = ""
    else:
        spec = repo / "docs/s1router/spec.md"
        spec.write_text(spec.read_text() + "\n| R-001 | Duplicate | Bad |\n")
    write_json(path, data)
    with pytest.raises(ValueError):
        gate.check_traceability(repo)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", []),
        ("code", ["scripts/check_repo.py"]),
        ("tests", []),
        ("tests", ["tests/tooling/test_checks.py::test_fake"]),
        ("tests", ["tests/product/missing.py"]),
    ],
)
def test_implemented_needs_real_product_paths(implemented: Path, field: str, value: Any) -> None:
    path = implemented / "docs/traceability.json"
    data = gate.read_json(path)
    data["R-001"][field] = value
    write_json(path, data)
    with pytest.raises(ValueError):
        gate.check_traceability(implemented)


@pytest.mark.parametrize(
    "mode",
    ["empty", "skipped", "unknown", "missing_lane", "uncollected", "unmarked", "no_behavior"],
)
def test_tests_must_be_collected_passing_and_requirement_linked(
    implemented: Path, mode: str
) -> None:
    report = passing_test_report(implemented)
    node = next(iter(report))
    if mode == "empty":
        report = {}
    elif mode == "skipped":
        report[node]["outcome"] = "skipped"
    elif mode == "unknown":
        report[node]["requirements"] = ["R-999"]
    elif mode == "missing_lane":
        for result in report.values():
            result["markers"] = ["behavioral"]
    elif mode == "uncollected":
        report.pop(node)
    elif mode == "unmarked":
        report[node]["requirements"] = []
    else:
        report[node]["markers"].remove("behavioral")
    with pytest.raises(ValueError):
        gate.check_test_report(implemented, report)


def test_complete_mapping_passes(implemented: Path) -> None:
    gate.check_test_report(implemented, passing_test_report(implemented))


@pytest.mark.parametrize("lines,branches", [(89, 100), (100, 84)])
def test_coverage_rejects_low_lines_or_branches(lines: int, branches: int) -> None:
    with pytest.raises(ValueError):
        gate.check_coverage(coverage_report(lines, branches))


def test_domain_coverage_is_stricter() -> None:
    with pytest.raises(ValueError, match="core.py"):
        gate.check_coverage(coverage_report(94, 94), product=True)
    gate.check_coverage(coverage_report(95, 95), product=True)
    gate.check_coverage(coverage_report(90, 85))


def test_empty_and_mixed_coverage_fail() -> None:
    data = coverage_report()
    data["files"] = {}
    with pytest.raises(ValueError, match="No coverage"):
        gate.check_coverage(data)
    data = coverage_report()
    data["files"]["scripts/tool.py"] = next(iter(data["files"].values()))
    with pytest.raises(ValueError, match="Mixed"):
        gate.check_coverage(data, product=True)
    data["totals"]["num_statements"] = 0
    with pytest.raises(ValueError, match="No executable"):
        gate.check_coverage(data)


def test_no_branch_module_still_requires_line_coverage() -> None:
    data = coverage_report()
    data["totals"]["num_branches"] = 0
    next(iter(data["files"].values()))["summary"]["num_branches"] = 0
    gate.check_coverage(data, product=True)
    data["files"]["packages/router/src/s1router/cli.py"] = {"summary": data["totals"]}
    gate.check_coverage(data, product=True)


def test_exact_risk_known_values() -> None:
    assert gate.risk_upper(0, 200) == pytest.approx(1 - 0.05 ** (1 / 200), abs=1e-12)
    assert gate.risk_upper(1, 2) == pytest.approx(math.sqrt(0.95), abs=1e-12)
    assert gate.risk_upper(2, 2) == 1
    assert gate.risk_upper(10, 200) > 0.05
    with pytest.raises(ValueError):
        gate.risk_upper(0, 0)


@pytest.mark.parametrize(
    ("group", "key", "value"),
    [
        ("quality", "accepted_count", 0),
        ("quality", "errors", 100),
        ("quality", "accepted_count", 300.0),
        ("quality", "eligible_count", 2000),
        ("quality", "ece", 0.06),
        ("quality", "nll", 0.8),
        ("quality", "brier", 0.6),
        ("quality", "ece", float("nan")),
        ("resources", "warm_p95_ms", 501),
        ("resources", "bundle_bytes", -1),
        ("resources", "peak_rss_bytes", float("inf")),
    ],
)
def test_release_quality_and_resource_failures(
    repo: Path, group: str, key: str, value: Any
) -> None:
    data = release_report(repo)
    data[group][key] = value
    write_json(repo / "reports/release.json", data)
    with pytest.raises(ValueError):
        gate.check_release(repo)


def test_release_hashes_and_review_fields(repo: Path) -> None:
    data = release_report(repo)
    gate.check_release(repo)
    for field, value in (("status", "released"), ("reviewer", ""), ("evidence", [])):
        bad = copy.deepcopy(data)
        bad[field] = value
        write_json(repo / "reports/release.json", bad)
        with pytest.raises(ValueError):
            gate.check_release(repo)
    write_json(repo / "reports/release.json", data)
    (repo / "reports/evidence.json").write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        gate.check_release(repo)


def test_release_rejects_stale_source_evidence(repo: Path) -> None:
    release_report(repo)
    spec = repo / "docs/s1router/spec.md"
    spec.write_text(spec.read_text() + "\nChanged acceptance behavior.\n")
    with pytest.raises(ValueError, match="source digest"):
        gate.check_release(repo)


@pytest.mark.parametrize("mode", ["foundation", "product", "release", "baseline", "coverage"])
def test_cli_dispatch_and_failure_codes(
    repo: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setattr(gate, "ROOT", repo)
    args = ["check_repo.py", mode]
    if mode == "baseline":
        args += ["--reason", "Reviewed fixture for CLI test"]
    elif mode == "coverage":
        write_json(repo / "coverage.json", coverage_report())
        args += ["coverage.json"]
    monkeypatch.setattr(sys, "argv", args)
    assert gate.main() == (1 if mode in ("product", "release") else 0)


def test_cli_missing_coverage_and_product_sources(
    implemented: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "ROOT", implemented)
    # Construct the missing-source condition explicitly now that S1M exists.
    shutil.rmtree(implemented / "packages/model/src")
    gate.refresh_baseline(implemented, "Reviewed fixture implementation mapping")
    monkeypatch.setattr(sys, "argv", ["check_repo.py", "coverage"])
    assert gate.main() == 1
    monkeypatch.setattr(sys, "argv", ["check_repo.py", "product"])
    assert gate.main() == 1
    for component in ("contracts", "model"):
        path = implemented / f"packages/{component}/src/module.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 1\n")
    assert gate.main() == 0
    release_report(implemented)
    monkeypatch.setattr(sys, "argv", ["check_repo.py", "release"])
    assert gate.main() == 0


def test_product_plugin_preserves_setup_teardown_and_xfail_failures() -> None:
    plugin = runner.ProductEvidence()
    for stage in ("setup", "call", "teardown"):
        plugin.results["test"] = {"outcome": "not_run"}
        report = pytest.TestReport("test", ("test.py", 1, "test"), {}, "passed", None, "call")
        plugin.pytest_runtest_logreport(report)
        assert plugin.results["test"]["outcome"] == "passed"
        report = pytest.TestReport("test", ("test.py", 1, "test"), {}, "failed", "error", stage)
        plugin.pytest_runtest_logreport(report)
        assert plugin.results["test"]["outcome"] == "failed_or_skipped"
    plugin.results["test"] = {"outcome": "not_run"}
    report = pytest.TestReport("test", ("test.py", 1, "test"), {}, "passed", None, "call")
    report.wasxfail = "expected"
    plugin.pytest_runtest_logreport(report)
    assert plugin.results["test"]["outcome"] == "failed_or_skipped"


def test_product_plugin_collects_real_pytest_markers(request: pytest.FixtureRequest) -> None:
    item = request.node
    item.add_marker(pytest.mark.requirement("R-001"))
    item.add_marker(pytest.mark.behavioral)
    plugin = runner.ProductEvidence()
    plugin.pytest_collection_modifyitems([item])
    result = plugin.results[item.nodeid]
    assert result["requirements"] == ["R-001"]
    assert "behavioral" in result["markers"]
    assert result["outcome"] == "not_run"


@pytest.mark.parametrize("result_code", [0, 1, 5])
def test_product_runner_propagates_test_and_evidence_failure(
    implemented: Path, monkeypatch: pytest.MonkeyPatch, result_code: int
) -> None:
    monkeypatch.chdir(implemented)
    monkeypatch.setattr(runner, "ROOT", implemented)

    def fake_pytest(args: list[str], plugins: list[runner.ProductEvidence]) -> int:
        assert "--cov-branch" in args
        plugins[0].results = passing_test_report(implemented)
        write_json(implemented / "reports/product-coverage.json", coverage_report())
        return result_code

    monkeypatch.setattr(pytest, "main", fake_pytest)
    assert runner.main() == result_code
    if result_code == 0:

        def missing_tests(args: list[str], plugins: list[runner.ProductEvidence]) -> int:
            return 0

        monkeypatch.setattr(pytest, "main", missing_tests)
        assert runner.main() == 1
