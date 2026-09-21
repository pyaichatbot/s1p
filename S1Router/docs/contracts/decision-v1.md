# Decision contract v1

Status: proposed normative shared kernel, 2026-09-19. This file owns interchange semantics for both products. Requirements R-001, R-004, R-007 and M-001, M-005, M-006 incorporate it. Design derives from [conversation primitives](../sources/conversation.md); exact fields and bounds below are project choices.

## Envelope

UTF-8 JSON, finite numbers, unique object keys, no unknown fields. Contract version is `1.0`; reject unknown versions until explicit compatibility exists. IDs are case-sensitive ASCII strings matching `[a-zA-Z0-9_.:-]{1,128}`. Byte limits apply before parsing; depth/count checks apply during bounded parsing.

Request fields:
- schema_version: "1.0"
- request_id: ID, identifies this run, not an idempotency guarantee across runs
- state: JSON object, maximum encoded envelope 256 KiB, maximum nesting depth 16
- language: BCP-47-like explicit tag, initially "en" for the registered task; declaration alone does not prove language support
- data_class: public | internal | restricted
- questions: ordered array, 1–32 independent questions
- constraints: object with deadline_ms (integer 1–60,000), allow_remote (Boolean), max_cost_usd (decimal string, nonnegative, at most six decimal places)

Call constraints may tighten policy; they cannot relax it. State is never merged into constraints. Effective deadline/cost is the minimum of call and policy ceilings; remote requires both call and policy permission. Each retrying caller starts a new run unless a future idempotency protocol is specified.

Question fields: id, task_id, task_version (positive integer), definition_hash (64 lowercase hex SHA-256), kind, instructions, and support. Instructions are at most 4,096 characters. The hash binds task state schema, supported languages, instructions and ordered support using deterministic UTF-8 JSON (sorted object keys, compact separators, no nonfinite numbers, Unicode preserved). Contract v1 schemas contain no floating-point values; runtime state is not part of this definition hash.

Kinds:
- choice: support array of 2–64 objects with unique id and nonempty description, each description ≤1,024 characters.
- bool: support exactly [{"id":"false","description":"False"},{"id":"true","description":"True"}].
- score: support array of 2–21 objects, each with unique id, integer value and nonempty rubric; values strictly increase and are within -1,000…1,000. Sparse integer scales are permitted. Expected value can be fractional.

Provider limits may be lower than contract limits. Capability checks use the exact registered definition hash; caller-supplied free-form questions do not imply model support.

## Prediction response (S1M and S1 provider port)

One item per requested question, in order:
- question_id
- status: predicted | unsupported | error
- probabilities: array in support order, each {id, probability}; null unless predicted
- selected_id: deterministic argmax, first declared support item breaks ties; null unless predicted
- p_true: number only for predicted bool, otherwise null
- expected_value: weighted sum of integer values for predicted score, otherwise null
- confidence: maximum probability for predicted items, otherwise null
- calibration_status: raw | calibrated | unavailable
- provenance: provider_id, model_ref, tokenizer_hash, preprocessor_hash, definition_hash, precision, runtime_version, calibration_ref (nullable)
- reason: registered reason code or null

Probabilities are finite in [0,1], complete and unique, and sum to one within absolute tolerance 1e-6. Derived quantities must match within 1e-6. Do not round intermediate values. Serialization uses enough precision to retain tolerance. A raw distribution is a prediction but not eligible for local automatic acceptance.

`calibrated` requires an applicable calibration profile bound to every relevant provenance field. A provider cannot create this label by asserting that its scores “look calibrated.” Model/task identity mismatch is explicit unsupported/error. For `status=unsupported` with `reason=unsupported_task`, provenance retains the actual installed task hash, which may differ from the requested hash; all probability/selection/derived fields must be null. Predicted results and other responses require the requested task hash. An unsupported result never authorizes an answer.

## Routing result (S1Router)

Envelope: schema_version, request_id, policy_ref, task_registry_ref, outcomes, timings_ms, cost_usd, audit_ref.

Each outcome: question_id, status (`answered_rule`, `answered_local`, `answered_remote`, `review_required`, `error`), selected_id (nullable), prediction (nullable object above), reason (nullable), attempts (ordered provider/rule identities, status, reason, elapsed_ms, cost_usd).

- answered_rule: selected_id and rule identity; prediction=null.
- answered_local: valid calibrated prediction and selected_id matching its argmax.
- answered_remote: valid selected_id from a permitted provider; prediction may be null if no calibrated distribution exists.
- review_required: selected_id=null. An optional prediction can carry a candidate, clearly unaccepted.
- error: selected_id=null, prediction=null, typed reason required.

A generated remote answer must select one support ID; do not fabricate a one-hot distribution from it. A rule also does not get a synthetic probability of 1. Every valid request has one outcome per question; infrastructure errors before evaluation use a separate request error envelope {schema_version, request_id, error:{code,message,retryable}}.

Review-needed is a successful abstention, not an exception. S1M never emits routing statuses. Unknown reason codes fail adapter validation until the contract explicitly extends them.

## Reason registry and capability failures

Version 1 reason values: unsupported_task, unsupported_language, input_too_long, too_many_choices, missing_calibration, calibration_mismatch, low_confidence, low_margin, rule_conflict, remote_disabled, data_policy, budget_exhausted, deadline_exceeded, provider_unavailable, invalid_provider_output, mandatory_review, audit_unavailable, invalid_request, invalid_configuration, invalid_contract_version, artifact_missing, artifact_corrupt, incompatible_runtime, queue_full, rate_limited, cancelled, inference_failed and internal_error. Success uses null, not an empty string. Request errors use these same codes.

Capabilities additionally return max_state_tokens, max_head_tokens, max_questions and max_choices, all positive integers. State and head limits are both evaluated against the full task rendering before execution. Provider-specific error strings belong in sanitized diagnostics, never as new wire enums. Exception messages must not reveal original state or credentials.

## Concrete request example

This shape is illustrative: definition_hash must be generated from the exact registered task before execution.

```json
{
  "schema_version": "1.0",
  "request_id": "demo-001",
  "state": {"title": "Fix crash on empty config", "body": "The command exits unexpectedly."},
  "language": "en",
  "data_class": "public",
  "questions": [{
    "id": "change_type",
    "task_id": "sdlc.change_type",
    "task_version": 1,
    "definition_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "kind": "choice",
    "instructions": "Classify the primary intended change.",
    "support": [
      {"id": "bug", "description": "Restore broken behavior"},
      {"id": "feature", "description": "Add behavior"},
      {"id": "documentation", "description": "Change explanatory material"},
      {"id": "refactor", "description": "Restructure without intended behavior change"}
    ]
  }],
  "constraints": {"deadline_ms": 5000, "allow_remote": false, "max_cost_usd": "0.000000"}
}
```

The all-zero example digest is deliberately non-executable and must fail registry matching. Product implementation must ship generated, schema-validated executable fixtures separately.

## Evolution and source of truth

Changing enum meaning, label/rubric semantics, confidence definition or unknown-field policy requires an explicit version/compatibility decision and consumer contract tests. Stable task IDs do not imply stable task definitions. Version schema, task, model, calibration and routing policy independently.

Reference rationale: [DDD shared context boundaries](https://martinfowler.com/bliki/BoundedContext.html), [calibration](https://proceedings.mlr.press/v70/guo17a.html). See [router specification](../s1router/spec.md) and [model specification](../s1m/spec.md) for behavior; neither may redefine these fields privately.

## Optional Jev bridge conformance

Project decision from [ADR-014](../decisions.md), informed by the [pinned upstream comparison](../research/jev-projects-comparison.md): external `noul` maps explicitly to our `bool`; index-based Score outputs require a checked mapping to declared integer values. Never silently reinterpret sparse levels. Missing/extra support keys, mismatched task identity, malformed distributions and incomplete answer sets are provider failures. Entropy confidence and prompted probabilities are not calibrated correctness probabilities. Rescaling an arbitrary vector does not satisfy this contract's distribution validation or calibration identity. A future adapter must pass conformance before enabling acceptance.

The L1 CLI additionally defines command-level `input_unavailable` and `invalid_configuration` errors, exit 4. These do not add model outcome statuses. [L1 spec](../layers/l1/spec.md).

## Audit validation and replay evidence

Audit records are a distinct redacted schema. Legacy audit version `1.0` contains exactly schema_version, policy_ref, task_registry_ref, input_sha256, cost_usd, duration_ms and outcomes. Hashes are lowercase SHA-256, monetary values are exact nonnegative six-decimal strings, duration is finite and nonnegative, and outcomes contain only ordered index/status/reason entries. Unknown fields, duplicate keys, invalid types, unsupported versions and records above 64 KiB are rejected before replay; records are never treated as instructions.

A verification-only replay compares supplied original request bytes and policy and explicitly reports missing artifact/registry evidence. It must not claim that matching hashes reproduce a decision. Actual replay additionally needs the original verified artifacts and deterministic execution evidence; outbound calls remain disabled in replay. Missing evidence stays a typed incomplete result. These rules refine R-008 without substituting a hash comparison for full execution replay.

Resident admission may return `rate_limited` (retryable), `input_too_long` for an oversized frame and `cancelled` for requests outside the ready lifecycle. These are registered request-error reasons; no original state or unvalidated identifiers are echoed in rejection diagnostics.
