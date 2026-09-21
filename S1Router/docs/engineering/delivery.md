# Deterministic development and local CI

Status: active foundation controls; proposed product/release standards, 2026-09-19. These implement the user's specification-led workflow. They reduce drift; they cannot guarantee agent compliance or semantic correctness. [Context](../sources/conversation.md)

## Toolchain and commands

Python 3.12.9. Exact direct pins: pytest 9.1.1, Ruff 0.16.8, mypy 2.3.1, coverage 7.16.1, pytest-cov 7.1.0, pytest-socket 0.8.1, Hypothesis 6.168.0, pip-audit 2.10.1. Resolved from PyPI on 2026-09-19; transitive versions/hashes are in uv.lock. Product ML dependencies are selected and locked during implementation.

- `make bootstrap`: explicit network-enabled locked development install.
- `make check`: offline foundation checks, lint, types, tooling tests/coverage.
- `make ci`: foundation plus complete product requirement mapping, product tests/coverage.
- `make audit`: explicit network-enabled dependency advisory audit.
- `make release`: product CI, audit and local release evidence.

Sources: [uv](https://docs.astral.sh/uv/concepts/projects/sync/), [Ruff](https://docs.astral.sh/ruff/), [pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html), [branch coverage](https://coverage.readthedocs.io/en/latest/branch.html).

## Gate levels

| Gate | Enforced | Limit |
| --- | --- | --- |
| Foundation | Required docs/links, source links, unique requirement IDs, complete registry, baseline hashes, agent TOML/skill metadata, lint, strict types, tooling tests/coverage | Does not certify product implementation |
| Product | All requirements mapped to existing code and collected/passed requirement-marked behavioral tests; no skip/xfail; package presence; separate product coverage; required test lanes | Intentionally fails before implementation |
| Release | Product gate, audit, hashed local evidence files, reviewed report and numeric quality/resource criteria | Human evidence integrity and semantic review remain necessary |

Tooling line coverage ≥90%, branch ≥85%. Product line ≥90%, branch ≥85%; each domain module line and branch ≥95%. Zero-branch modules have branch coverage 100% only with executable statements. No exclusions to hide untested product files. No-test collection fails.

Each requirement needs at least one passing test with both requirement("R-001") or M ID and behavioral markers. All mapped tests must pass. Product CI also requires contract, architecture, and integration lanes. Lint/types cover all code. Hardware/network experiments are separate deliberate lanes. Foundation checks also compare direct development pins to the lockfile and installed tool versions; lockfile/interpreter files are covered by the reviewed baseline.

Socket blocking catches Python socket use, not malicious subprocess networking; tests must not launch network-capable subprocesses.

## Drift and development workflow

Every product requirement appears exactly once in the specs and registry. Entries record status, implementation files, actual pytest node IDs and acceptance intent. Baseline hashes cover product/shared/engineering documents, instructions, configuration and skill definitions.

Workflow: requirement → scenario → meaningful failing test → implementation → refactor → gates → review. Public contract changes update both consumer specifications and conformance tests.

After reviewing the actual diff, refresh explicitly:
` .venv/bin/python scripts/check_repo.py baseline --reason "Describe reviewed change and decision reference" `

This records a reason, not owner approval. Never run it as an automatic repair for unexplained drift.

Architectural tests reject domain imports of adapters/CLI, tensor/HTTP dependencies in router domain, router-policy dependencies in S1M, and inference imports of training/evaluation. Check absolute and relative imports. Adapters share one provider conformance suite.

## Release evidence

Local reports/release.json has status="candidate", reviewer, owner_decision_ref, revision, source_digest, evidence, quality and resources. source_digest is computed by scripts.check_repo.source_digest over the normative baseline files, Python product/tool/test sources, interpreter file and lockfile; a mismatch rejects stale evidence. Each evidence entry has purpose, path and sha256. Required purposes: model_quality, hardware, dataset_provenance, artifact_manifest, rollback_drill, privacy_drill, adapter_conformance, dependency_audit.

Each underlying report records commands, versions, timestamps, immutable inputs, exit statuses and results. Evidence must come from real runs; fixtures cannot certify release. The reviewer verifies that summary metrics match underlying reports.

Quality fields: accepted_count ≥200, errors, eligible_count ≥accepted_count, ece ≤0.05, nll/brier no worse than baseline_nll/baseline_brier. The gate recomputes accepted coverage ≥0.30 and exact one-sided 95% binomial risk upper bound ≤0.05.

Resources: bundle_bytes ≤1,073,741,824; peak_rss_bytes ≤4,294,967,296; warm_p95_ms ≤500; cold_p95_ms ≤15,000; router_p95_ms ≤10. Values must be positive and finite. File hashes and numerical checks do not prove honest measurement.

Release also requires license/provenance review, clean install, offline operation, failure drills, runtime compatibility and rollback evidence. Start exposure in shadow mode, then a bounded canary. Roll back on accepted-error breach, missing required audit, artifact mismatch, privacy violation or persistent provider failure. Never automatically retrain from live outputs.

## Hooks and adoption

.githooks/pre-commit runs foundation checks; pre-push runs product CI. Opt in with `make hooks` after initializing a Git repository. Hooks are bypassable and do not replace branch protection. Hosting CI should invoke the same commands. No remote repository is configured.

Custom roles: s1-architect, s1-router-engineer, s1-model-engineer, s1-verifier. Agents live in .codex/agents and skills in .agents/skills. [Codex agents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [skills](https://learn.chatgpt.com/docs/build-skills).

## Remaining work

The owner has directed progressive implementation through local deployment, observation and maintenance. Each scoped layer runs its own gate while the full-product gate remains intact. See [layered delivery](layered-delivery.md) and [L1 spec](../layers/l1/spec.md). A layer release does not certify a trained model or full product. [Decision register](../decisions.md)

## Work tracking and source adoption

Use [Kanban](kanban.md) and the repository s1-delivery-loop skill for every scoped change. Plan/design/build/test/deploy/observe/maintain stages retain actual evidence; routine local layers do not require another approval ceremony. Public release remains evidence-gated. New upstream code requires immutable source revision, retained license/NOTICE, exact dependency pins and separate model/data provenance review. Upstream benchmark reports or captured inputs cannot substitute for this project's release evidence. [ADR-014](../decisions.md) records current research candidates.

## Product maintainability gate

[Code quality](code-quality.md) is normative: SOLID review, maximum 249 physical lines per production source file, justified design patterns, strict dependency boundaries and behavior-preserving refactoring. `make architecture` runs the same checks included in `make check`, layer CI and full CI. Semantic review remains necessary; passing a line count is not an architecture assessment.
