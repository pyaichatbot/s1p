"""Collect product behavior evidence, run coverage, and reject incomplete mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.check_repo import ROOT, check_coverage, check_test_report


class ProductEvidence:
    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            self.results[item.nodeid] = {
                "outcome": "not_run",
                "requirements": [
                    mark.args[0] for mark in item.iter_markers("requirement") if mark.args
                ],
                "markers": [mark.name for mark in item.iter_markers()],
            }

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        record = self.results[report.nodeid]
        if report.failed or report.skipped or hasattr(report, "wasxfail"):
            record["outcome"] = "failed_or_skipped"
        elif report.when == "call" and record["outcome"] == "not_run":
            record["outcome"] = "passed"


def main() -> int:
    plugin = ProductEvidence()
    sources = sorted(Path("packages").glob("*/src"))
    args = [
        "-p",
        "pytest_cov",
        "-p",
        "pytest_socket",
        "tests/product",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=json:reports/product-coverage.json",
    ]
    args.extend(f"--cov={p}" for p in sources)
    result = pytest.main(args, plugins=[plugin])
    Path("reports").mkdir(exist_ok=True)
    Path("reports/product-tests.json").write_text(json.dumps(plugin.results, indent=2) + "\n")
    if result != pytest.ExitCode.OK:
        return int(result)
    try:
        check_test_report(ROOT, plugin.results)
        coverage = json.loads(Path("reports/product-coverage.json").read_text())
        check_coverage(coverage, product=True)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
