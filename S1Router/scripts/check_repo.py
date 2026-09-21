"""Fail-closed local documentation, traceability, coverage and evidence checks."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = [
    f"docs/{product}/{name}.md"
    for product in ("s1router", "s1m")
    for name in ("intent", "design", "spec")
]
REQUIRED_DOCS += [
    "docs/README.md",
    "docs/contracts/decision-v1.md",
    "docs/engineering/delivery.md",
    "docs/engineering/layered-delivery.md",
    "docs/engineering/kanban.md",
    "docs/engineering/code-quality.md",
    "docs/engineering/full-router-plan.md",
    "docs/layers/l1/spec.md",
    "docs/layers/l1/plan.md",
    "docs/layers/l1/operations.md",
    "docs/research/jev-projects-comparison.md",
    "docs/research/jev-model-router-comparison.md",
    "docs/sources/README.md",
    "docs/sources/conversation.md",
    "docs/decisions.md",
    "AGENTS.md",
]
EVIDENCE_PURPOSES = {
    "model_quality",
    "hardware",
    "dataset_provenance",
    "artifact_manifest",
    "rollback_drill",
    "privacy_drill",
    "adapter_conformance",
    "dependency_audit",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), f"Path escapes repository: {relative}")
    require(path.is_file(), f"Missing file: {relative}")
    return path


def baseline_paths(root: Path) -> list[Path]:
    paths = [root / name for name in REQUIRED_DOCS]
    paths.extend((root / ".codex").rglob("*.toml"))
    paths.extend((root / ".agents").rglob("SKILL.md"))
    paths.extend(
        root / p
        for p in (
            "pyproject.toml",
            "uv.lock",
            ".python-version",
            "Makefile",
            "docs/traceability.json",
            "docs/layers/l1/manifest.json",
        )
    )
    return sorted(set(paths))


def check_toolchain(root: Path) -> None:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    locked = tomllib.loads((root / "uv.lock").read_text())
    versions = {package["name"]: package["version"] for package in locked["package"]}
    for dependency in project["dependency-groups"]["dev"]:
        require("==" in dependency, f"Unpinned development dependency: {dependency}")
        name, expected = dependency.split("==", maxsplit=1)
        require(versions.get(name) == expected, f"Lockfile mismatch: {name}")
        actual = importlib.metadata.version(name)
        require(actual == expected, f"Installed version mismatch: {name}; run make bootstrap")


def refresh_baseline(root: Path, reason: str) -> None:
    require(len(reason.strip()) >= 12, "A meaningful reviewed-change reason is required")
    data = {
        "schema_version": 1,
        "review_reason": reason,
        "sha256": {str(p.relative_to(root)): digest(p) for p in baseline_paths(root)},
    }
    (root / "docs/baseline.json").write_text(json.dumps(data, indent=2) + "\n")


def check_baseline(root: Path) -> None:
    baseline = read_json(root / "docs/baseline.json")
    actual = {str(p.relative_to(root)): digest(p) for p in baseline_paths(root)}
    require(baseline["sha256"] == actual, "Baseline drift: review changes before rebaselining")


def source_digest(root: Path) -> str:
    paths = baseline_paths(root)
    for directory in ("packages", "scripts", "tests"):
        paths.extend((root / directory).rglob("*.py"))
        paths.extend((root / directory).rglob("*.mjs"))
    for name in ("uv.lock", ".python-version"):
        if (root / name).is_file():
            paths.append(root / name)
    records = {str(p.relative_to(root)): digest(p) for p in sorted(set(paths))}
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def check_docs(root: Path) -> None:
    for name in REQUIRED_DOCS:
        local_file(root, name)
    paths = [root / "AGENTS.md", *(root / "docs").rglob("*.md")]
    paths.extend((root / ".agents").rglob("SKILL.md"))
    for path in paths:
        body = path.read_text()
        require(body.startswith(("# ", "---\n")), f"Missing heading/frontmatter: {path}")
        require(bool(re.search(r"\[[^\]]+\]\([^)]+\)", body)), f"Missing source/link: {path}")
        require(not re.search(r"\b(?:TODO|TBD|FIXME)\b", body), f"Unresolved placeholder: {path}")
        for line in body.splitlines():
            require(line == line.rstrip(), f"Trailing whitespace: {path}")
        prose = re.sub(r"\x60{3}.*?\x60{3}", "", body, flags=re.S)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", prose):
            target = target.strip("<>").split("#")[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (path.parent / target).resolve()
            require(resolved.exists(), f"Broken local link in {path}: {target}")


def check_agents(root: Path) -> None:
    agents = sorted((root / ".codex/agents").glob("*.toml"))
    require(
        {
            "s1-architect",
            "s1-router-engineer",
            "s1-model-engineer",
            "s1-verifier",
            "s1-delivery-coordinator",
        }
        <= {path.stem for path in agents},
        "Missing project agent roles",
    )
    for path in agents:
        data = tomllib.loads(path.read_text())
        for key in ("name", "description", "developer_instructions"):
            require(isinstance(data.get(key), str) and bool(data[key].strip()), f"{path}: {key}")
        require(data["name"] == path.stem, f"Agent name/file mismatch: {path}")
    tomllib.loads((root / ".codex/config.toml").read_text())
    skills = sorted((root / ".agents/skills").glob("*/SKILL.md"))
    require(
        {
            "s1-implement",
            "s1-spec-change",
            "s1-model-evaluation",
            "s1-release-check",
            "s1-kanban",
            "s1-delivery-loop",
        }
        <= {path.parent.name for path in skills},
        "Missing repository skills",
    )
    for path in skills:
        body = path.read_text()
        match = re.match(r"---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n", body)
        require(match is not None, f"Invalid skill metadata: {path}")
        assert match is not None
        require(match.group(1) == path.parent.name, f"Skill name mismatch: {path}")


def check_traceability(root: Path, product: bool = False) -> dict[str, Any]:
    ids: list[str] = []
    for name in ("s1router", "s1m"):
        body = (root / f"docs/{name}/spec.md").read_text()
        ids.extend(re.findall(r"^\| ([RM]-\d{3}) \|", body, flags=re.M))
    for spec in (root / "docs/layers").glob("*/spec.md"):
        ids.extend(re.findall(r"^\| (L[0-9]+-\d{3}) \|", spec.read_text(), flags=re.M))
    require(len(ids) == len(set(ids)), "Duplicate specification requirement IDs")
    data: dict[str, Any] = read_json(root / "docs/traceability.json")
    require(set(ids) == set(data), "Traceability IDs differ from specification requirements")
    for rid, entry in data.items():
        require(entry["status"] in {"planned", "implemented"}, f"Invalid status for {rid}")
        require(bool(entry["acceptance"]), f"Missing acceptance intent for {rid}")
        if product:
            require(entry["status"] == "implemented", f"{rid} is not implemented")
        if entry["status"] == "implemented":
            require(bool(entry["code"]) and bool(entry["tests"]), f"Missing evidence for {rid}")
            for code in entry["code"]:
                require(code.startswith("packages/"), f"{rid}: code must be product code")
                local_file(root, code)
            for node in entry["tests"]:
                require(node.startswith("tests/product/") and "::" in node, f"Invalid node: {node}")
                local_file(root, node.split("::")[0])
    return data


def check_test_report(root: Path, report: dict[str, Any], selected: set[str] | None = None) -> None:
    registry = check_traceability(root, product=selected is None)
    if selected is not None:
        require(bool(selected) and selected <= set(registry), "Unknown layer requirements")
        for rid in selected:
            require(registry[rid]["status"] == "implemented", f"{rid} is not implemented")
    require(bool(report), "No product tests collected")
    lanes: set[str] = set()
    for node, result in report.items():
        require(result["outcome"] == "passed", f"Product test did not pass: {node}")
        lanes.update(result["markers"])
        for rid in result["requirements"]:
            require(rid in registry, f"Unknown requirement marker {rid} in {node}")
    require(
        {"behavioral", "contract", "architecture", "integration"} <= lanes, "Missing test lanes"
    )
    for rid, entry in registry.items():
        if selected is not None and rid not in selected:
            continue
        for node in entry["tests"]:
            require(node in report, f"Uncollected requirement test: {node}")
            result = report[node]
            require(rid in result["requirements"], f"Missing {rid} marker: {node}")
        require(
            any("behavioral" in report[node]["markers"] for node in entry["tests"]),
            f"No behavioral acceptance test for {rid}",
        )


def check_coverage(data: dict[str, Any], product: bool = False) -> None:
    files = data["files"]
    require(bool(files), "No coverage files measured")

    def assess(summary: dict[str, Any], line_min: float, branch_min: float, label: str) -> None:
        statements = summary["num_statements"]
        branches = summary["num_branches"]
        require(statements > 0, f"No executable statements measured: {label}")
        lines = 100 * summary["covered_lines"] / statements
        branch_pct = 100 * summary["covered_branches"] / branches if branches else 100
        require(lines >= line_min, f"{label}: line coverage {lines:.2f}% < {line_min}%")
        require(
            branch_pct >= branch_min, f"{label}: branch coverage {branch_pct:.2f}% < {branch_min}%"
        )

    assess(data["totals"], 90, 85, "total")
    if product:
        require(all(name.startswith("packages/") for name in files), "Mixed product/tool coverage")
        for name, value in files.items():
            if "/domain/" in name and value["summary"]["num_statements"]:
                assess(value["summary"], 95, 95, name)


def risk_upper(errors: int, accepted: int) -> float:
    """Invert the binomial CDF for a one-sided exact 95% upper confidence bound."""
    require(0 <= errors <= accepted and accepted > 0, "Invalid accepted/error counts")
    if errors == accepted:
        return 1.0

    def log_cdf(p: float) -> float:
        terms = [
            math.lgamma(accepted + 1)
            - math.lgamma(i + 1)
            - math.lgamma(accepted - i + 1)
            + i * math.log(p)
            + (accepted - i) * math.log1p(-p)
            for i in range(errors + 1)
        ]
        peak = max(terms)
        return peak + math.log(sum(math.exp(t - peak) for t in terms))

    low, high = 1e-15, 1 - 1e-15
    for _ in range(80):
        mid = (low + high) / 2
        if log_cdf(mid) > math.log(0.05):
            low = mid
        else:
            high = mid
    return high


def check_release(root: Path) -> None:
    report = read_json(root / "reports/release.json")
    require(report["status"] == "candidate", "Release report must be a candidate")
    require(report["source_digest"] == source_digest(root), "Release source digest is stale")
    for field in ("reviewer", "owner_decision_ref", "revision"):
        require(bool(report[field].strip()), f"Missing release {field}")
    purposes = {e["purpose"] for e in report["evidence"]}
    require(EVIDENCE_PURPOSES <= purposes, "Missing release evidence categories")
    for entry in report["evidence"]:
        path = local_file(root, entry["path"])
        require(digest(path) == entry["sha256"], f"Evidence hash mismatch: {path}")
    quality = report["quality"]
    n, k, eligible = (quality[key] for key in ("accepted_count", "errors", "eligible_count"))
    require(all(type(v) is int for v in (n, k, eligible)), "Counts must be integers")
    require(eligible >= n >= 200 and 0 <= k <= n, "Insufficient/invalid accepted evidence")
    require(n / eligible >= 0.30, "Insufficient local coverage")
    require(risk_upper(k, n) <= 0.05, "Accepted risk confidence bound exceeds 5%")
    for key in ("ece", "nll", "brier", "baseline_nll", "baseline_brier"):
        value = quality[key]
        require(type(value) in (float, int) and math.isfinite(value) and value >= 0, f"Bad {key}")
    require(quality["ece"] <= 0.05, "ECE exceeds 5%")
    require(quality["nll"] <= quality["baseline_nll"], "NLL regresses baseline")
    require(quality["brier"] <= quality["baseline_brier"], "Brier regresses baseline")
    limits = {
        "bundle_bytes": 1_073_741_824,
        "peak_rss_bytes": 4_294_967_296,
        "warm_p95_ms": 500,
        "cold_p95_ms": 15_000,
        "router_p95_ms": 10,
    }
    for key, maximum in limits.items():
        value = report["resources"][key]
        require(
            type(value) in (float, int) and math.isfinite(value) and 0 < value <= maximum,
            f"Resource gate failed: {key}",
        )


def foundation(root: Path) -> None:
    check_toolchain(root)
    check_docs(root)
    check_agents(root)
    check_traceability(root)
    check_baseline(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=["foundation", "product", "release", "baseline", "coverage"]
    )
    parser.add_argument("report", nargs="?")
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    try:
        if args.mode == "baseline":
            refresh_baseline(ROOT, args.reason)
        elif args.mode == "coverage":
            require(bool(args.report), "Coverage report path required")
            check_coverage(read_json(ROOT / args.report))
        else:
            foundation(ROOT)
            if args.mode in ("product", "release"):
                check_traceability(ROOT, product=True)
                for component in ("contracts", "router", "model"):
                    require(
                        any((ROOT / f"packages/{component}/src").rglob("*.py")),
                        f"Missing {component} product source",
                    )
            if args.mode == "release":
                check_release(ROOT)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
