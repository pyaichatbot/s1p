# L1 Local Runtime Implementation Plan

> **For agentic workers:** Use the repository s1-implement workflow task by task. Execute inline in the current workspace under the owner's instruction to continue through working local layers.

**Goal:** Deliver a locally installed deterministic decision command with bounded telemetry, observation and rollback.

**Architecture:** Standard-library-only contracts and pure rule domain; filesystem/CLI/deployment adapters. No model dependencies, external services or listeners.

**Tech Stack:** Python 3.12.9; existing locked pytest/Ruff/mypy/coverage tooling.

**Spec:** [L1 specification](spec.md), [NFR design](../../engineering/layered-delivery.md).

## Global constraints

256 KiB request; nesting depth 16; 1–32 questions; no outbound I/O; no fake probabilities; private bounded event storage. Gate line coverage ≥90%, branch ≥85%, each domain module ≥95% for both. Local layer success is separate from full-product release.

## Review focus

- Oversized/deep input must fail before expensive processing; parser exceptions must not leak raw state.
- Caller mutation must not alter the registered task or rule behavior.
- Disk/audit failure must not return an automatic answer.
- Corrupt monitoring input must be visible rather than counted as healthy.
- Tampered/partial releases must never activate; rollback must retain mutable operator data.

## Tasks and exact interfaces

### 1. Contract and pure routing

Files: packages/contracts/src/s1_contracts/request.py, packages/router/src/s1router/domain/rules.py, packages/router/src/s1router/domain/admission.py; tests/product/test_local_domain.py.

Produces parse_request(raw: bytes) -> dict[str, Any], example_request() -> dict[str, Any], decide(request: dict[str, Any]) -> dict[str, Any], TokenBucket(rate: float, burst: int, clock: Callable[[], float]).allow() -> bool.

- [x] Write behavior tests for valid example, unknown/duplicate/nonfinite/deep input, malformed support, rule answer, abstention, task mutation, bucket refill and backward clock.
- [x] Run tests and confirm missing behavior fails.
- [x] Implement strict bounded parser, fixed task registry, explicit metadata rule, abstention and token bucket.
- [x] Run contract/domain/property tests and strict types.

Example acceptance:
```python
request = example_request()
request["state"]["declared_change_type"] = "bug"
assert decide(request)["outcomes"][0]["status"] == "answered_rule"
```

### 2. Local telemetry and CLI

Files: packages/router/src/s1router/telemetry.py, packages/router/src/s1router/cli.py, packages/router/src/s1router/__main__.py; tests/product/test_local_operations.py.

Consumes parse_request/decide. Produces EventStore(directory: Path).append(status, reason, duration_ms, release_id), observe(directory: Path) -> dict[str, Any], CLI main(argv: list[str] | None) -> int.

- [x] Write real temporary-filesystem tests for event privacy, rotation, retention, corruption, alert thresholds, incident deduplication, CLI JSON/exits and audit failure.
- [x] Run the failing scenarios before implementation.
- [x] Implement bounded storage, deterministic summaries and CLI commands.
- [x] Run full layer behavior and architecture tests.

### 3. Layer gate and local deployment

Files: scripts/run_layer_ci.py, packages/router/src/s1router/deployment.py, Makefile, docs/layers/l1/manifest.json; tests/tooling/test_layers.py and tests/product/test_local_deployment.py.

Consumes actual pytest evidence and product coverage; preserves strict full-product checks. Produces `make layer L=1`, deploy/rollback/status commands and local launcher.

- [x] Test that missing/failed layer behavior or unknown layer cannot pass; full product still fails incomplete R/M IDs.
- [x] Test snapshot integrity, same-source idempotence, activation and rollback using isolated temporary deployments.
- [x] Implement exact layer manifest validation and source snapshot deployment.
- [x] Run make check and make layer L=1.

### 4. Deploy, observe, maintain

- [x] Deploy the verified layer under .local/s1/releases and activate it.
- [x] Run the installed CLI outside the checkout; exercise successful rule, abstention, invalid input and health.
- [x] Observe a controlled malformed-event incident in an isolated drill directory. Diagnose, record evidence and verify its regression test.
- [x] Exercise rollback with two verified snapshots; retain evidence in docs/layers/l1/operations.md.
- [x] Review the whole change against the spec and update this ledger with results and limitations.

## Execution ledger

Ruling: proceed inline with reversible local work, as requested; no new approval ceremony for each layer. Public release and paid model compute remain separate decisions.

Ruling: L1 deliberately deploys a CLI snapshot rather than introducing a service just to demonstrate operations. The rate-limit primitive is tested now and enforced by a resident runtime in L2.

Source of truth: [spec](spec.md) and [owner-directed layered workflow](../../engineering/layered-delivery.md).

Completed 2026-09-20. Exact commands, measurements, review findings and remaining full-product limits are retained in [operations evidence](operations.md). The local deployment artifact is rules-only; broader R/M work remains planned.
