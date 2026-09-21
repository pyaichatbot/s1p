# Progressive delivery and operations

Status: adopted development approach, 2026-09-19. Owner direction: continue through working layers; local deployment counts; observe and maintain each layer; keep NFRs explicit without premature infrastructure.

## Lifecycle

The [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook), published 2026-08-21, describes connected plan/design/build/test/deploy/maintain stages, durable artifacts, and deterministic monitoring that feeds findings back into intent. We apply that lifecycle to this repository using Codex, local commands and versioned evidence. Vendor-specific products and example approval scripts are not prerequisites.

Each layer has a bounded spec and plan, real code, behavioral tests, local deployment instructions, observations and a maintenance record. The owner's instruction to proceed authorizes this routine local loop. Ask only for genuinely missing business decisions or actions outside that authorization, such as paid compute, external publication or broader operational access.

## Product layers

| Layer | Working outcome | Deployment/feedback | Completion gate |
| --- | --- | --- | --- |
| L0 — foundation | Product intent, architecture, contracts, sources and tools | Local document/tool validation | make check |
| L1 — deterministic local runtime | Strict request admission, exact rule decisions, explicit abstention, JSON CLI | Immutable local snapshot, audit/health, observation and rollback drill | make layer L=1 |
| L2 — model inference | Verified local checkpoint adapter, capability checks, proper distribution validation, calibrated gating | One resident worker, bounded queue, per-artifact latency and health | Contract/conformance, hardware smoke, shadow evaluation |
| L3 — adaptive routing | Explicit remote adapter, budgets, cancellation, circuit breaker, mixed-question routing | Local gateway integration with fault drills | Routing and privacy/budget tests, gateway conformance |
| L4 — S1M specialization | Reviewed data, leakage-resistant splits, train/calibrate/evaluate/export | Experimental model bundles; frozen test evidence | Model-quality and resource gates |
| L5 — operational service | Optional authenticated shared service, per-principal rate limiting, measured worker scaling | Local/private deployment, controlled canary and operational acceptance | Full make ci and applicable make release profile |

Layers accumulate capability; they are not technical tiers where all design finishes before coding. L2/L4 model research must not block shipping a useful L1. A passing layer is labeled by its capabilities and limitations, never as full S1M/router readiness. All full-product requirements remain tracked.

## NFR matrix and activation

All values below are initial project settings or targets, not claims derived from the playbook.

| Concern | Local design and measurable control | Activate / escalation trigger |
| --- | --- | --- |
| Correctness | Strict schema; no fabricated probabilities; mandatory abstention on unsupported inputs | L1; property/negative tests |
| Observability | Redacted structured events, outcome/reason counts, processing latency, release ID; health/doctor command | L1; model/queue/network stages added in L2/L3 |
| Availability | Explicit health failure; valid requests never appear successful after audit failure; no 99.9% promise for a laptop | L1; shared-service SLO only after stable measured operation |
| Latency | Rules-only p95 ≤10 ms application processing on reference laptop; CLI/process startup measured separately | L1; model/resource targets remain in S1M spec |
| Rate limiting | Resident runtime token bucket: 10 requests/sec, burst 20; one-shot CLI is not a shared quota service | L1 reusable admission primitive; enforce on resident worker at L2 |
| Backpressure | One inference at a time, max pending 32, bounded frames, reject saturation with retryable reason | L2 worker; L1 single synchronous CLI has no queue |
| Scalability | Batch compatible questions, reuse loaded model, load-test before increasing workers; memory budget per worker | L2; move to multiple workers only when measured queue waits violate target |
| Resource/cost bounds | 256 KiB request, depth 16, max 32 questions; remote disabled; bounded telemetry storage | L1; atomic monetary reservations in L3 |
| Reliability | Typed errors, monotonic deadlines, no blind retries, known-good snapshot rollback | L1 local rollback; cancellation/circuit breaker in L3 |
| Privacy/security | No raw state/IDs/secrets in default events, private local files, no input-supplied endpoints or executable rules | L1; authentication/TLS required before non-loopback service at L5 |
| Persistence/durability | Synchronous metadata write before returning an automatic answer; bounded rotation; explicit audit failure | L1; durable external sink only for deployment requiring it |
| Recovery | Retain previous local release; target operator rollback ≤60 s; audit RPO last successful synchronous write, subject to disk guarantees | L1 drill; model/config pair rollback in L2/L3 |
| Compatibility | Version request, task, policy and deployment; exact task definition matching | L1; consumer and exported-runtime conformance in L2 |
| Maintainability | Pure domain core, adapters for I/O, requirement-linked tests, lockfile, one source of truth | Every layer |
| Monitoring quality | Minimum 20 samples before rate alerts; fixed thresholds until enough baseline exists; incident deduplication | L1; learned statistical bands only after stable history |
| Retention | Event segments at most 1 MiB each, current plus one backup; age purge after seven days when accessed | L1; document gaps from rotation/purge |
| Supply chain | Explicit artifact install, known digests, pinned tools; snapshot manifest verifies source bytes | L1 source snapshots; signed/trusted model origin in L2 |
| Accessibility/operator UX | Machine-readable stdout, diagnostics on stderr, stable exit codes, actionable commands | L1 CLI; UI accessibility only if a UI is added |

## Monitoring and maintenance

Local commands examine bounded event files. Initial control bands: non-validation processing error rate >5% with ≥20 samples; invalid-request rate >20% with ≥20 samples; processing p95 >10 ms with ≥20 samples. Any audit-write failure is immediately actionable via command failure/doctor; a broken audit sink cannot reliably report itself into that sink.

No-traffic is insufficient evidence, not a healthy latency claim. Observation reports sample count, time range and data gaps. Reports exclude raw input. A finding writes a deduplicated local incident with evidence, impact, hypothesis, reproduction, proposed fix, regression test and closure state; it does not mutate code, change thresholds or retrain by itself.

During active development, deploy → exercise success and failure paths → observe → diagnose → regression test → fix → rerun layer gate → redeploy. A long-lived scheduled agent monitor is a later explicit operational choice; a deterministic observe command already supports this loop without introducing a daemon or recurring AI bill.

## Simplicity boundaries

No Kubernetes, distributed rate limiter, Kafka, database cluster, service mesh, autoscaling, tracing collector or dashboards in L1. Add an external metrics sink only when a consumer needs one. Keep telemetry fields compatible with later export, but do not build unused exporter abstractions.

A local release is an immutable code snapshot with a verified manifest and atomic active pointer. No production secrets or public listening port is required. State stays outside snapshots so rollback preserves telemetry and incidents. Full multi-process serving remains gated by shared-rate-limit and concurrency tests.

Source of truth: [router design](../s1router/design.md), [model design](../s1m/design.md), [full gates](delivery.md), and [L1 specification](../layers/l1/spec.md).

## Research-informed later layers

L3 may evaluate a LocalJev adapter with fault/conformance drills; L4 may evaluate jev-align-style acquisition and annotation. Both remain optional and outside L1. Later provider observations include provider type, model/runner revision, calibration status, queue/retry counts and whether state crossed a local boundary, without raw state or high-cardinality metric labels. Source and limitations: [pinned upstream comparison](../research/jev-projects-comparison.md), [ADR-014](../decisions.md).
