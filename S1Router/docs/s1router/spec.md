# S1Router — executable behavior specification

Status: proposed full specification, version 0.1, 2026-09-19. MUST denotes a project release requirement. No requirement below is currently claimed implemented. Test mappings live in [traceability](../traceability.json).

S1Router accepts state and typed questions and returns typed outcomes after policy-governed routing. It owns neither model training nor downstream action execution. Product scope derives from [C1](../sources/conversation.md); architecture is in [design](design.md).

## Normative contract

Implement [decision-v1](../contracts/decision-v1.md). Support SDK and JSON CLI with identical validation. Unknown fields, duplicate JSON keys, non-finite values, unsupported contract majors, duplicate IDs, invalid rubrics and oversized payloads MUST fail before a provider or audit payload writer receives state.

## Functional requirements

| ID | MUST behavior | Observable acceptance |
| --- | --- | --- |
| R-001 | Validate canonical requests and provider outputs at trust boundaries | Malformed probability, missing option, duplicate question, NaN and unknown fields fail; zero provider calls on bad request |
| R-002 | Snapshot immutable policy and apply deterministic rules in priority order | Same input/snapshot gives same routing; equal-priority conflicting matches require review |
| R-003 | Check task/rubric identity, supported language, full rendered token budgets and choice count before local evaluation | Unsupported inputs abstain without local inference, even if a mocked provider would return 0.999 |
| R-004 | Require artifact-matched calibration and configured probability/margin gates for local automatic acceptance | Below/equal/above threshold tested; Bool false-confidence and Score exact-bin semantics tested |
| R-005 | Route unresolved questions through a finite configured provider sequence, ending in answer or review | Maximum one attempt per provider per question; disabled remote yields no outbound calls |
| R-006 | Enforce endpoint/data policy, deadline, and atomic request budget reservation on every remote attempt | Concurrent attempts cannot overspend reserved limit; timeout/cancellation settles ledger and ignores late answer |
| R-007 | Preserve question order, isolate failures, and return exactly one terminal outcome for each valid question | Mixed accepted/unsupported/timeout batch returns complete per-question results without duplicate work |
| R-008 | Emit redacted versioned decision records and support explicit replay | No state/secret in default logs; replay reports missing original inputs; mandatory audit failure blocks automatic answers |
| R-009 | Implement SDK, JSON CLI, and bounded local worker with declared capabilities | CLI parses identically to SDK; frame bounds, queue-full, readiness, shutdown and stderr separation tested |
| R-010 | Support explicit model installation, integrity checks, offline operation, and atomic rollback | Corrupt/partial artifact never becomes active; offline inference never downloads |
| R-011 | Implement health isolation, circuit breaker, configuration validation and metrics | Fake clock verifies open/half-open/closed transitions; no high-cardinality or sensitive metric labels |
| R-012 | Separate recommendations from actions and mandatory review policy | No tool execution or review exemption; injected state cannot alter permissions, rules, endpoints or thresholds |
| R-013 | Pass task-risk, performance and fault-recovery release evidence | Same held-out cases across baselines; measured router overhead; rollback and provider outage drills pass |

## Behavioral scenarios

### Rules and gating

Given a matching approved deterministic rule, when `decide` runs, then the rule result includes rule ID/version, has null model probabilities, and invokes no model.

Given two contradictory matching rules with equal priority, then status is `review_required` with reason `rule_conflict`.

Given Bool P(true)=0.04 and an exact-label gate of 0.90, then the selected answer is false with confidence 0.96, subject to other policy gates. This does not permit bypassing a mandatory review policy.

Given top probability exactly 0.90, margin 0.25 and thresholds 0.90/0.10, then a supported calibrated prediction passes. Changing calibration identity, language to unsupported, or precision without recalibration causes abstention.

Given Score levels [1,2,3,4,5] and probabilities [0.05,0.05,0.10,0.70,0.10], then expected value is 3.75, selected level is 4, confidence is 0.70; a 0.90 acceptance threshold fails.

### Escalation and operational failures

Given a local abstention and remote disabled, return review-required and no network calls.

Given a valid remote answer with self-reported 0.99 confidence, retain confidence as null in the canonical result unless independently supported by the required calibration mechanism. Default remote policy returns review-required with a candidate answer.

Given a local answer for question A and malformed remote output for B, A remains valid, B ends in review-required, and A is never resent remotely.

Given the request deadline expires while inference runs, return the terminal deadline outcome and discard late results. The implementation must bound/terminate worker execution so cancellation is not merely cancellation of an await.

Given policy changes during execution, all attempts retain the starting policy hash.

Given a checksum mismatch or expired artifact acceptance profile, no automatic model answer is returned. Rollback selects a complete previous model/calibration/policy tuple.

## Default policy profile

Proposed defaults: remote disabled; audit_required=true; one local provider; optional one remote fallback; probability threshold 0.90; top-two margin 0.10; request deadline 5,000 ms; no retries; remote cost ceiling zero until explicitly configured. Thresholds are candidate settings, not release evidence. Task-specific profiles are tuned using calibration data only and may be stricter.

Supported first automatic task: `sdlc.change_type@1`, English short issue title/body, exactly bug/feature/documentation/refactor. Ambiguous or mixed changes require review; no fifth class is silently added. Questions for unsupported tasks still receive typed abstention and can use a permitted remote fallback.

## CLI surface and errors

Planned commands: `s1 decide FILE --json`, `s1 doctor --json`, `s1 policy validate FILE`, `s1 replay RECORD --state FILE`, `s1 worker`, and explicit `s1 model install ARTIFACT_REF`. JSON results only on stdout. Exit 0 means all questions answered; 2 means invalid input/configuration; 3 means one or more review-required results; 4 means infrastructure/request failure. Diagnostic stderr never contains raw sensitive state.

Review reasons include unsupported_task, unsupported_language, input_too_long, too_many_choices, missing_calibration, calibration_mismatch, low_confidence, low_margin, rule_conflict, remote_disabled, data_policy, budget_exhausted, deadline_exceeded, provider_unavailable, invalid_provider_output, mandatory_review and audit_unavailable.

## Nonfunctional acceptance

Router-only warm p95 ≤10 ms for 10,000 requests with one question and a fake provider; publish p50/p95/p99, concurrency=1, payload distribution and machine conditions. Queue maximum 32, deterministic queue-full rejection, no unbounded retry/task creation. Test memory stability over 10,000 requests separately from ML runtime memory.

For eligible held-out issue questions, model-only local coverage ≥30% and one-sided 95% exact binomial upper bound of accepted error ≤5%, with at least 200 locally accepted questions. Report request-level and per-question rates separately, including invalid/out-of-envelope traffic denominators. Baselines: majority, rules, sparse classifier, local checkpoint and configured remote model on identical reviewed test cases. Remote unavailable means no remote-comparison claim.

Operational release requires clean installation, offline test, concurrent budget tests, cancellation, provider outage, invalid artifact, full disk/audit failure and rollback drills. Tests and gates are defined in [delivery](../engineering/delivery.md); coverage does not replace these behaviors. [Q4](https://coverage.readthedocs.io/en/latest/branch.html)

## Evidence basis

Calibration methodology: [Guo et al.](https://proceedings.mlr.press/v70/guo17a.html). Risk/coverage: [selective classification](https://arxiv.org/abs/1705.08500). All budgets and thresholds above are local product decisions. A production release must satisfy this spec, the [shared contract](../contracts/decision-v1.md), and the [release evidence policy](../engineering/delivery.md).

## Progressive delivery and operational scope

The owner-directed [layered delivery and NFR matrix](../engineering/layered-delivery.md) is part of this product design. Every delivered layer must build, test, deploy locally, observe and maintain its actual capabilities. Full-product readiness is not required to release a clearly scoped local layer; model quality and all future capabilities remain separately gated.

## Mandatory code-quality constraints

Owner-directed [CQ-001–CQ-004](../engineering/code-quality.md) apply to this product: SOLID responsibilities and dependency inversion, narrow substitutable ports, fewer than 250 physical lines per production source file, and justified patterns without speculative abstraction. Mechanical size/import checks run in every local gate; independent semantic review records design rationale and behavioral evidence. Resource bounds and scalability follow the progressive NFR design; a small file alone proves neither. Source decision: [ADR-015](../decisions.md).

## Existing-runtime review clarification (2026-09-21)

Owner scope: review and repair implemented behavior; FEAT-007/008 remain deferred.
R-009/R-011 rejection paths must use registered reason codes, bound echoed identifiers,
reject deeply nested input without crashing, and invoke output callbacks outside admission
locks. SIGTERM must not acquire worker locks inside its handler; normal and exceptional
stdio exit must drain accepted work and restore the previous handler. R-006 failures
finishing an attempt must clear any tentative automatic answer. These are hardening
acceptance scenarios for existing controls, not new model lifecycle features.
