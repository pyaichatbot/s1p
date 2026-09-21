# L1 local deployment and maintenance evidence

Executed 2026-09-20 on macOS 26.5.2 arm64, Python 3.12.9, Node 22.22.0. Scope: [L1-001–L1-006](spec.md) and [KB-001–KB-005](../../engineering/kanban.md). Sources: [actual verification summary](evidence/verification.json), [observation](evidence/observation.json), [maintenance drill](evidence/maintenance.json). These are measured local results, not full-product/model readiness.

## Verification and activation

- `make deploy-local` passed: Ruff lint/format, strict mypy, document/agent/traceability baseline, 69 tooling tests, 5 Kanban behavioral tests and 20 layer product tests. No skipped or expected-failure tests.
- Tooling: 98.81% lines, 94.00% branches. Layer product: 96.69% lines, 91.79% branches; both domain modules 100% lines/branches. Kanban CLI: 100% lines, 92.42% branches. Gates remain 90% lines/85% branches and 95%/95% per domain module.
- Activated release `1d4e12d1c28f7bee6dbec08ea22b91bb1ba83c983d9f2091f87b15b3ef636c52` under `.local/s1/releases`, selected by the atomic active pointer. `.local/s1/bin/s1` is the installed launcher. The local owner controls the manifest: checks detect accidental corruption; they do not provide signed supply-chain authenticity.
- `make local-smoke` passed from a temporary working directory outside the checkout: example, rule answer, abstention, invalid input, doctor, observe. `make local-status` verified the active release.
- `make ci` exits 2 because R-001 remains planned. All broader R/M requirements remain unimplemented; model loading, remote fallback, resident concurrency and training are future layers. No gate was weakened to make L1 pass.

## Observation

The installed CLI processed the smoke requests and 20 additional synthetic rule requests. The retained window contains 23 events: 21 rule answers, 1 invalid input, 1 review outcome, 0 processing errors. Processing p95 was approximately 0.241 ms, excluding process startup and audit I/O. No threshold findings occurred. This is a tiny synthetic sanity check, not load capacity, latency SLO or model quality evidence. The observer explicitly reports incomplete history because retention/rotation may leave gaps.

Audit metadata includes only release, timestamp, fixed status/reason and duration. State is outside snapshots; request bodies are not logged. Default event segments are each bounded at 1 MiB, with one backup and seven-day retention on access. The CLI has no network listener. Rate limiting is a tested primitive in L1; cross-request enforcement starts with the resident L2 runtime.

## Controlled incident and recovery

In an isolated temporary state directory, a synthetic malformed line caused observe to return exit 3 and telemetry_corrupt. An incident record was created. The drill preserved the 28 corrupt bytes in a private operator copy, removed only the known malformed live record, appended a valid metadata event and observed again. Findings cleared; the result correctly remained insufficient_data with one valid event. The temporary drill did not alter the deployed runtime's state. Sanitized before/after evidence is retained above; no missing records were fabricated.

Independent runtime review also discovered malformed nested/large-numeric telemetry crashes, task-schema bypass, invalid release configuration, corrupt-active rollback failure and incident deduplication drift. Each was reproduced with a failing behavioral test, fixed and rerun. Kanban review found an evidence-refresh dead end; explicit reviewed replacement now retains the prior hash, and Done items must reopen first.

Rollback was exercised in isolated filesystem tests with two distinct verified snapshots, repeated same-source deployment, tampering, recovery from a corrupt active snapshot and refusal of a corrupt target. The live installation has its first release, so `make rollback-local` will correctly fail until another verified revision has been deployed. Mutable telemetry remains outside release directories.

## Operator procedure

```sh
make local-status
.local/s1/bin/s1 doctor
.local/s1/bin/s1 observe --record-incident
make local-smoke
```

For a finding, retain the sanitized incident, create a requirement-linked BUG via the [Kanban CLI](../../engineering/kanban.md), reproduce with a regression, repair, run `make layer L=1`, then `make deploy-local` and observe again. For corrupted audit files, preserve a private copy before narrowly repairing invalid records; never silently reconstruct a complete history. Snapshot corruption is repaired by a verified rollback target; preserve the damaged snapshot for diagnosis. Repeated routine checks are operator-invoked; no background scheduler or AI monitor has been installed.

Review evidence: independent `review_l1_runtime` agent reviewed runtime, deployment, Kanban, ADR-014 and lifecycle skills; findings were resolved through the regression tests described above. The root agent reviewed the final changes and source boundaries. This records review, not owner approval of full production release.

## Owner follow-up: maintainability and additional research

After the initial deployment, CQ-001–CQ-004 added a 249-physical-line production-source cap, import-boundary checks and mandatory semantic SOLID review. The existing deployed product did not need source changes; its snapshot ID remains unchanged. Independent review found no blocking issue, verified all current files meet the cap (largest 217), and confirmed distinct responsibilities without unnecessary pattern scaffolding.

The expanded tooling suite now has 80 passing tests, including 11 architecture scenarios. Kanban has 6 passing behavioral tests, including reviewed scope updates, with 100% line and 92.54% branch coverage. The 20 product acceptance tests remain passing. The initial deployment measurements above retain their original scope; [final quality verification](evidence/quality-verification.json) records this later check. The additional [host-template research](../../research/jev-model-router-comparison.md) was completed by the root agent after Luna's usage-limit failure; no external plugin was installed or executed.
