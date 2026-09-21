# L1 — deterministic local runtime specification

Status: authorized for progressive local implementation by the owner's 2026-09-19 direction. Scope: strict request admission, rules and abstention, operator evidence, local deployment and a maintenance loop. Sources: [layered NFR design](../../engineering/layered-delivery.md), [shared contract](../../contracts/decision-v1.md), [router specification](../../s1router/spec.md).

This is a capability-limited first release. It does not load a model, call a remote provider or claim completion of broad R/M requirements. L1 IDs below are explicit narrower acceptance units; the full requirements remain planned until their complete behavior passes.

| ID | MUST behavior | Observable acceptance |
| --- | --- | --- |
| L1-001 | Admit canonical v1 requests with bounded parsing and strict fields/types/support/hash shape | Duplicate keys, excessive bytes/depth, unknown fields, nonfinite numbers, Boolean-as-integer and malformed rubrics fail before processing |
| L1-002 | Use an immutable registered task and explicit rules to answer or abstain | English issue state with trusted declared_change_type matching a label yields a rule answer; unmatched/unsupported task/language yields review; input cannot enable remote calls |
| L1-003 | Provide process-local token-bucket admission using a monotonic clock | Burst 20, refill 10/sec; rejected attempt does not consume future tokens; backward clock never adds tokens; configuration invalidity fails |
| L1-004 | Record bounded private redacted events and derive deterministic observations | No raw state/ID; current and backup segments bounded; malformed evidence reported; minimum sample gates; repeated incident deduplicated |
| L1-005 | Expose runnable decide/example/doctor/observe commands with canonical JSON and stable exits | Installed local snapshot works outside checkout; stdout parses; invalid input=2, review=3, I/O/audit failure=4; diagnostic data contains no original input |
| L1-006 | Verify immutable local release snapshots, atomic activation and rollback | Tampered release rejected; previous verified release restored; deployment, observation and regression evidence recorded |

## Concrete rules-only task

Task definition `sdlc.change_type@1` uses the four labels and instructions in decision-v1. Its definition hash also includes state_schema and languages. State schema accepts title/body strings and optional declared_change_type; the latter is explicitly caller-provided metadata, not inferred from prose. This rule is a convenience for trusted callers, not a security decision. Unknown state metadata is permitted by the outer JSON contract but not consulted by this rule.

Malformed registered title/body state yields review_required/invalid_request. Invalid release configuration returns exit 4 with invalid_configuration; unreadable input returns input_unavailable. Corrupt telemetry makes doctor fail; an externally oversized segment requires operator repair before new writes, preserving evidence.

Only exact recognized label metadata can produce answered_rule. Missing/unrecognized metadata returns review_required/remote_disabled. A language other than en returns unsupported_language. A different task ID, version or definition hash returns unsupported_task. Requests remain valid even when the task is unsupported.

The task description is never executed and text keywords are never treated as truth. Questions remain independent and return in order. Model prediction is always null in L1. All outcomes use policy_ref `local-rules@1` and immutable task_registry_ref. No fabricated distribution is emitted.

## Operational envelope

L1 deployment is a local command snapshot, not an HTTP server. It serves one synchronous request per invocation. The token bucket is a tested reusable admission primitive; per-principal quota across multiple CLI processes activates with the resident/shared-service layers. L1 cannot claim distributed/global rate limiting.

Audit events contain timestamp, release ID, status, fixed reason code and duration_ms only. No input state, task prose or caller IDs. Segment limit defaults to 1 MiB, one backup, retention seven days. Private directory 0700 and files 0600 on POSIX. Audit failure prevents success. Observation inspects at most two bounded segments, reports corrupt records and explicitly marks history incomplete because retention/rotation may leave gaps, and emits findings according to layered NFR thresholds.

`s1 observe --record-incident` creates local incident Markdown with source/runbook links and stable deduplication by finding type plus release. Combined observations create one record per finding; the CLI returns the primary record path and the other records remain in the same incident directory. It never edits product intent automatically; a maintained incident is promoted to a scoped change through the normal spec/test workflow. No scheduled AI monitor is implicitly enabled.

## Deployment and acceptance

`make deploy-local` runs the L1 gate before snapshot/activation. Snapshots include product Python sources and an integrity manifest, with a generated launcher using the current Python 3.12 interpreter. Mutable telemetry/incident data remains outside release directories. This is local deployment to the current machine, not a portable wheel distribution.

`make local-smoke` exercises an installed command, successful rule, abstention, malformed request, health and observation. `make rollback-local` selects the preceding verified snapshot. Deploying identical source is idempotent and must not erase the previous revision. Retain old snapshots until explicitly removed by the operator.

Layer acceptance: all six IDs mapped to passing tests, no skipped/xfail tests, same line/branch/domain coverage thresholds as full product, plus local deployment/observation evidence. `make ci` remains the full-product gate and still requires all R/M requirements.
