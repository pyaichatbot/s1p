# Architecture decisions

Status: proposed baseline, 2026-09-19. Owner changes require a dated entry with affected requirement IDs. These are local engineering decisions, informed by [conversation](sources/conversation.md), [DDD](https://martinfowler.com/bliki/BoundedContext.html), and [ports/adapters](https://alistair.cockburn.us/hexagonal-architecture).

| ID | Decision | Alternatives and trade-off |
| --- | --- | --- |
| ADR-001 | Python 3.12 product target; modular monorepo with separately installable contracts, router, and model packages | TypeScript router plus Python service improves native npm ergonomics but adds a protocol/deployment boundary before value is proven. Python JSON CLI is the initial bridge. |
| ADR-002 | S1Router owns routing; S1M owns model lifecycle; shared contract contains no ML dependency | A single integrated model/router package is faster initially but couples policy to research releases. Microservices introduce premature operations. |
| ADR-003 | Choice, Bool, and finite ordinal Score use distributions; no free-text reasoning in S1M | Generated JSON is allowed only inside a remote adapter, and cannot pretend to be calibrated logits. |
| ADR-004 | Laya is the first integration candidate; custom SDLC encoder/head is S1M's independent training path | Constrained small autoregressive models and sparse classifiers are baselines; none are mandatory dependencies of the router. |
| ADR-005 | Explicit task registry, domain/language envelope, token and choice limits precede local inference | Max-probability alone cannot establish support. A generic OOD detector is not promised. |
| ADR-006 | Immutable model/preprocessor/calibration/policy versions; no training in the request path | Online self-updating models complicate rollback and invalidate evidence. |
| ADR-007 | SDK and JSON CLI first; long-lived local worker for amortized loading; optional internal HTTP service later in full release | A per-call subprocess is simple but measures repeated cold starts; a managed multi-tenant cloud service is outside scope. |
| ADR-008 | Human escalation is an explicit pending result; caller owns execution and review UX | Embedding workflow execution would blur prediction, authorization, and side effects. |
| ADR-009 | Remote disabled by default; endpoint allowlist and data policy are checked on every attempt | Gateway access alone is not permission to transmit state. |
| ADR-010 | Initial automatic task is issue change_type; additional Bool/Score tasks need independent evidence | An apparently complete multi-task demo does not justify high-impact automatic decisions. |
| ADR-011 | Local gates distinguish foundation, product, and release evidence | Passing documentation checks must never appear as product readiness. |
| ADR-012 | Reproducible workflow, deterministic domain core, statistical ML reproducibility | Cross-device bitwise equality and universally deterministic agent behavior are not achievable guarantees. |

## Release stages

Foundation (L0, delivered): complete proposed documents, traceability, agent definitions, skills, and executable local gates.

First vertical slice: contracts, deterministic fake backend, rules, CLI, abstention, one real local baseline, one explicitly configured remote adapter, evaluation. Training does not block this milestone.

S1M experiment: licensed datasets, split isolation, sparse baseline, encoder/head training, calibration, export and comparative report. A failed experiment remains an honest result.

Production candidate: required product behaviors, hardware measurements, task-specific release criteria, bounded concurrency, incident/rollback drills, audited distributions, locked artifacts, clean offline verification. These are deliverables, not a weekend promise.

## Change protocol

Record date, rationale, superseded decision, owner decision reference, changed requirements, migration needs, and new acceptance tests. Refresh the document digest only after reviewing the actual diff. A digest detects file changes; it cannot establish semantic agreement or owner approval.

## ADR-013 — progressive local delivery (2026-09-19)

Owner direction supersedes treating documentation as the stopping point. Adopt [layered delivery](engineering/layered-delivery.md): each bounded layer plans, builds, tests, deploys locally, observes and feeds issues back into maintenance. Keep full-product release thresholds; add explicit layer gates so incomplete future capabilities do not prevent validating current ones. NFRs are designed now and activated where they become relevant. The [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) supplies the lifecycle framing; deployment choices and control values are ours.

## ADR-014 — delivery tracking and upstream candidates (2026-09-20)

Owner direction: maintain repository Kanban and use Luna/high for the requested research. Adopt [Kanban controls](engineering/kanban.md), one coordinator role and two focused workflow skills. JSON is authoritative; offline HTML is a generated view. Status and lifecycle stage are separate; completion requires evidence and review rather than an agent's unsupported declaration.

The [pinned comparison](research/jev-projects-comparison.md) informs existing R-001/R-003/R-004/R-005/R-007 and M-003/M-008 requirements. LocalJev is an optional L3 adapter candidate, not a calibrated S1M replacement. Its generated probabilities have unavailable calibration until artifact/task-bound evaluation establishes otherwise. jev-align informs optional L4 acquisition and annotation; it is not an inference dependency. No upstream package is installed by this decision, and broad requirement status remains planned.

## ADR-015 — small cohesive product modules (2026-09-20)

Owner constraint: follow SOLID, keep router/model files below 250 lines, and apply patterns only when needed. Adopt [CQ-001–CQ-004](engineering/code-quality.md) across shared contracts and product source: maximum 249 physical lines, explicit dependency boundaries, conformance tests for substitutable ports, and semantic reviewer evidence. Counting all physical lines is a conservative enforceable interpretation; splitting must preserve cohesion and readability. Mechanical checks do not claim to prove SOLID or scalability. No implementation threshold is relaxed, no model stub is introduced, and existing L1 modules already satisfy the size constraint.

## ADR-016 — optional host routing reference (2026-09-20)

The requested [Jev model-router review](research/jev-model-router-comparison.md) adds a host-integration reference alongside ADR-014's bridge and alignment references. Reuse ideas around pure policy, asymmetric error costs, turn-scoped decision reuse and deliberate no-change outcomes. Do not adopt upstream confidence defaults, mutable aliases, raw error logs, uncancelled timeout behavior or implicit outbound permissions. Host model/effort control is a later consumer adapter that respects explicit owner model choices and host capabilities; it is outside L1 and is not an S1M replacement. No external mod is installed.

## ADR-017 — bounded resident worker as the R-009 vertical slice (2026-09-20)

Scope decision for R-009 ("Implement SDK, JSON CLI, and bounded local worker with declared capabilities"). Per [design](s1router/design.md#deployment-resources-and-operations), implement the persistent local worker as length-bounded JSON lines over stdin/stdout, logs to stderr, single-inference concurrency, queue bound 32, and readiness published only after manifest verification plus a fixture smoke test. This is additive: the existing L1-005 `s1 decide`/`doctor`/`observe` CLI commands (already implemented, tested and deployed) are unchanged. Adding a new `s1 worker` command avoids regressing shipped L1 behavior while satisfying the frame-bounds/queue-full/readiness/shutdown/stderr-separation acceptance text.

"CLI parses identically to SDK" is satisfied by having the worker's frame handler delegate directly to the same `s1router.application.engine.Router.decide` used by SDK callers, rather than re-implementing request parsing. Queue admission and single-inference concurrency are implemented as a plain, injectable, thread-free-to-test core (`WorkerService.submit`/`run_once`) so behavioral tests can force exact queue-full and shutdown interleavings with a barrier, matching the existing R-006/R-011 concurrency test style, without depending on real process stdio. The full `s1 worker` stdio wiring (reader/writer threads, SIGTERM handling) is a thin adapter over that core. Multi-worker scaling and HTTP hosting remain out of scope, per design's "no distributed infrastructure is required for the local CLI."

## ADR-018 — `s1 model install` and `s1 policy validate` as thin CLI wrappers (2026-09-20)

Spec's [CLI surface](s1router/spec.md#cli-surface-and-errors) names `s1 policy validate FILE` and explicit `s1 model install ARTIFACT_REF` alongside `s1 decide`/`doctor`/`replay`/`worker`. Both wrap already-implemented, already-tested library behavior — `s1router.domain.policy.validate`/`PolicySnapshot.from_dict` (R-002) and `s1m.artifacts.bundle.install` (R-010) — with no new domain decision logic, so this is evidence attached to R-002 and R-010 respectively, not a new requirement ID.

`s1 policy validate FILE` reads a JSON policy config, runs the same `PolicySnapshot.from_dict` validation the router applies at snapshot time, and reports the resulting `policy_ref` on success; a rejected config returns `invalid_configuration` with exit 2, matching spec's CLI exit-code contract (0/2/4). `s1 model install SOURCE [--root PATH]` wraps `bundle.install` directly — no new atomicity or verification logic — and defaults `--root` to `$S1_HOME/models`, the same convention `s1 worker --model PATH` already expects an installed root to follow, so a human operator can now go from a built bundle to a running worker without writing Python. Both commands are additive: `decide`/`example`/`doctor`/`observe`/`worker` are unchanged. `s1 replay RECORD --state FILE` (R-008) remains out of scope for this decision and stays a follow-on card.

## ADR-019 — `s1 replay` reports hash reproducibility, never reconstructs input (2026-09-20)

Scope decision for R-008's replay half ("support explicit replay"; acceptance: "replay reports missing original inputs"). Design is explicit that this must not be faked: "Replay can use stored sanitized fixtures or caller-supplied state plus original artifact hashes; it must identify missing data instead of pretending a hash reconstructs input." A redacted audit record (the `record` dict `Router.decide` passes to `AuditSink.append`) never contains raw state — only `input_sha256`, `policy_ref`, `task_registry_ref` and per-question status/reason — so there is no raw request to feed back into `Router.decide` and no honest way to "re-run" a decision from a record alone.

`s1 replay RECORD --state FILE [--policy FILE]` therefore does exactly one thing: it hashes the caller-supplied `--state` bytes and compares them to `record["input_sha256"]`, reporting `"verified"` or `"missing_original_input"` rather than silently trusting the caller's file is the original. An optional `--policy FILE` is checked the same way against `record["policy_ref"]` (`"verified"` / `"mismatch"` / `"not_supplied"` when omitted). `task_registry` is reported as `"not_verifiable"` unconditionally — there is no on-disk task-registry-by-hash store to check it against, and ADR-018's own precedent (don't manufacture capability the code doesn't have) applies here too. Exit 0 only when input is verified and policy is not a mismatch; otherwise exit 3 (review-required, matching the CLI's existing convention that 3 means "needs a human to look," not an infrastructure error). New pure logic lives in `application/replay.py` per design's module map ("application/ # decide, replay, validate configuration"); `cli.py` only adds file I/O and the record's JSON-shape check, same thin-wrapper pattern as ADR-018.
