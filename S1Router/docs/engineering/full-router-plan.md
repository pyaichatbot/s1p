# Full S1Router delivery plan

Status: active owner goal, 2026-09-20. Complete local-model inference, calibrated acceptance, remote fallback, budgets/deadlines, bounded service concurrency/rate limiting and a green full local CI gate. Sources: [router spec](../s1router/spec.md), [shared contract](../contracts/decision-v1.md), [model spec](../s1m/spec.md), [code quality](code-quality.md), [delivery controls](delivery.md). OSS router projects remain inspiration only.

## Completion boundary

Preserve every R-001–R-013 acceptance condition and existing `make ci`. That command currently also checks M-001–M-013: implement and verify needed model lifecycle work rather than delete mappings or claim fixtures satisfy measured release evidence. Model-quality evidence requires reviewed independent real data, two human labels/adjudication, pinned artifact provenance and reference-hardware measurements. Software can progress before those inputs are available; missing evidence remains explicitly incomplete. Full green CI and completed product are goals, not labels for the current L1 snapshot.

## Ordered work and evidence

1. R-001/R-004: strict prediction validation, complete support and derived quantities; trusted immutable calibration profiles with full identity and expiry; threshold/margin/Bool/Score/mandatory-review cases.
2. R-002/R-003/R-012: immutable validated policy/task snapshots, deterministic declarative rules with conflict handling, full rendered token/capability checks and data restrictions. No state-derived authorization.
3. R-005/R-006/R-007/R-011: finite provider orchestration, process-bounded cancellation, integer-microdollar reservations, endpoint allowlists, deadlines, per-question isolation and circuit health. Late results cannot alter terminal outcomes or erase incurred cost.
4. R-008/R-009: SDK/CLI parity, bounded worker frames and queue, persistent rate/concurrency limits, startup readiness/shutdown, redacted decision records, explicit replay and metrics.
5. R-010 and model dependencies: install and verify a real local inference artifact explicitly, immutable model/calibration/policy tuple, offline provider, invalid upgrade/rollback drills, and model lifecycle controls. No fabricated distributions or unverified calibration labels.
6. R-013: 10,000-request router latency/memory protocol, fault drills and held-out quality/baseline evidence. Keep experimental model results distinct from approved release profiles.
7. Full verification: actual requirement-to-test mappings, strict lint/types/architecture, no skipped tests, unchanged coverage thresholds, dependency audit, clean installation, local deployment, observation and maintenance record. `make ci` and applicable release evidence must describe their true scope.

Each step starts with failing behavioral scenarios and stays below 250 physical lines per product source file. Kanban FEAT-005 through FEAT-008 track related work; broad requirement IDs remain planned until their entire acceptance is verified. Execution may span goal turns without shrinking this completion boundary.

## Initial implementation decisions

Prediction admission rejects unknown fields, malformed provenance, incomplete/reordered support, invalid numeric types, invalid derived values and unknown reasons with a sanitized invalid_provider_output. A calibrated label is only a provider assertion until the acceptance gate matches a trusted profile to the complete provenance tuple. The profile also records calibration-data identity, expiry and thresholds. Gate equality passes; missing or stale identity abstains. Mutable input dictionaries are copied at the boundary and cannot mutate trusted profile identity.

The L1 domain-import test's narrow initial allowlist is extended only to pure `re`, `dataclasses` and `decimal`, already permitted by CQ-002; no I/O or ML dependency is enabled. Decimal comparison of serialized numeric values preserves the defined equality behavior for acceptance margins without changing provider distributions.

Policy implementation uses frozen values, unique finite provider IDs, explicit remote endpoint/data-class permissions and an immutable rule tuple. Higher numeric rule priority wins; conflicting matches at the highest matching priority require review. Task support compares the complete registered definition, not just a caller-supplied hash. Token counts are supplied by the installed provider's declared tokenizer for the complete state and head rendering, never a generic heuristic substituted for its limits.

## Execution record — full-product implementation in progress

The first implementation pass added canonical prediction admission, immutable artifact-bound calibration gates, policy snapshots, registered task/capability validation, request budget/deadline primitives, generation-bound circuit permits, provider/audit ports and SDK orchestration. Fifty focused scenarios pass; the full product test collection currently reports 70 passing and five failing tests, all five from the not-yet-implemented local model package. These are intermediate results, not completion of R-001–R-013.

Luna/high was used for execution controls and the local model artifact task. Both agents hit a usage limit. The root inspected their actual files: execution controls exist and were integrated with additional review fixes; the model task left only tests, not a runtime. Root continues these tasks directly rather than treating the failed agents as live work.

Remaining immediate work: finish the real sparse baseline artifact/runtime, correct its incomplete experimental fixtures to include actual file hashes and honest precision, provide production adapters with process-bounded cancellation, expand orchestration failure/concurrency tests, and wire SDK behavior through CLI/resident worker. A remote provider's generated confidence must never confer calibrated status. Current adapters are test doubles; no live remote compatibility claim exists. Full provider-tokenizer rendering and immutable execution identities need end-to-end adapter evidence.

The SDK preserves policy per run, isolates question outcomes, returns no automatic answer on audit failure, and records no original request ID/state in its audit payload. The input SHA-256 is only a replay commitment and is not anonymization. Budget overruns flag a violated ledger, retain conservative charges and prohibit new reservations. Trusted production configuration requires mandatory audit. No external OSS host-router code has been integrated.

Full CI is still red: model implementation, broader mappings, final tests and release evidence remain incomplete. No requirement has been marked implemented merely because these focused tests pass. Human-reviewed independent evaluation-data provenance has been requested while implementation continues.

### Offline sparse baseline implementation contract

The first numerical backend is an explicitly experimental sparse linear softmax model, stored as JSON weights and evaluated in Python float64. It is a baseline for adapter and lifecycle validation, not a claim that the planned encoder or model-quality release is complete. Bundles include the complete registered task, exact tokenizer/preprocessor definitions, license text, and SHA-256 hashes of every payload file. Empty hash tables, extra payloads, symlinks and mismatched precision are invalid. Installation verifies before atomic activation; inference reads a verified installed snapshot and never downloads. Temperature fitting/approved calibration is a separate lifecycle step: this baseline emits raw probabilities and cannot self-authorize automatic acceptance.

Artifact tests inherited from the interrupted worker contained empty hashes, placeholder calibration identities, an fp32 claim for stdlib arithmetic, and a repair attempt while a malicious symlink still existed. These fixtures must be corrected to test the stated integrity contract; malformed bundles must not be accepted to satisfy those draft tests. Shared task/capability admission belongs in the contract package so S1M does not depend on router policy. R-006/R-011 also require forged completion permits to leave genuine requests intact and malformed/overflowing clock values to fail before state mutation.

The initial offline baseline now executes real sparse-weight arithmetic for Choice, Bool and Score, verifies payloads before activation, and recovers a verified prior bundle after active corruption. It supports experimental_fixture artifacts only; release export and calibrated profiles remain later work. No artifact or weight was downloaded. Current tests include socket denial, preflight before numerical calls, malformed hashes/precision/calibration metadata, failed upgrades and rollback. This does not yet bound inference using a worker process or establish production quality.

The first local provider adapter will isolate each inference attempt in a child process, pass only bounded JSON, pin the verified content-addressed bundle, and kill/reap the child on timeout. This favors a simple enforceable deadline over warm-start performance in the experimental lane. A resident service and reference-laptop latency evidence remain required; this choice must not be presented as satisfying their throughput targets.

## Review remediation — 2026-09-21

Owner authorized fixing the complete review and completing both products. BUG-015 tracks reproduced deployment, worker and artifact defects. Clean-installed commands and child inference must use only the verified installed packages, without inheriting checkout PYTHONPATH. Worker intake must enforce bounds before allocation, stop promptly while stdin is idle, reject traffic outside its ready lifecycle, enforce the documented 10/sec burst-20 admission rate, and expose bounded metrics. Readiness requires successful real local inference as well as a durable audit write. Model active/previous pointers must resolve to the installation's exact verified content-addressed release; external redirects cannot become rollback targets. Typed artifact errors must survive adapter boundaries.

The owner selected open data with a prepared human-review workflow. Training/calibration and final human evaluation remain separate. Source rights must be verified before importing records, and two independent human labels plus adjudication remain the final-test release standard. No fixture, generated label or agent self-review can substitute for those labels. Completing software work continues while this evidence is assembled.

The previous execution records above are historical. Current baseline software contains a sparse runtime and worker, but review reproduced a broken clean installation and incomplete operational controls. Historical L1 deployment evidence does not cover later source additions. No model-quality release has been demonstrated. All corrected completion claims must identify current code, commands, measured evidence and limitations.
