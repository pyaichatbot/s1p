"""Run a narrowly enumerated layer without weakening the full-product gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.check_repo import ROOT, check_coverage, check_test_report, require
from scripts.run_product_ci import ProductEvidence


def requirements(layer: str) -> set[str]:
    require(layer == "1", "Unknown layer")
    manifest = json.loads((ROOT / "docs/layers/l1/manifest.json").read_text())
    selected = set(manifest["requirements"])
    require(selected == {f"L1-{i:03d}" for i in range(1, 7)}, "Incomplete layer manifest")
    return selected


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) == 1, "Specify one layer")
        selected = requirements(args[0])
        plugin = ProductEvidence()
        result = pytest.main(
            [
                "-p",
                "pytest_cov",
                "-p",
                "pytest_socket",
                "tests/product",
                "--cov-branch",
                "--cov=packages/contracts/src",
                "--cov=packages/router/src",
                "--cov-report=term-missing",
                "--cov-report=json:reports/l1-coverage.json",
            ],
            plugins=[plugin],
        )
        Path("reports").mkdir(exist_ok=True)
        Path("reports/l1-tests.json").write_text(json.dumps(plugin.results, indent=2) + "\n")
        require(result == pytest.ExitCode.OK, "Layer tests failed")
        check_test_report(ROOT, plugin.results, selected)
        check_coverage(json.loads(Path("reports/l1-coverage.json").read_text()), product=True)
        print("PASS: L1 scoped acceptance; full-product release remains separate")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
