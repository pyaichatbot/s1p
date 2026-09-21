# Product code quality contract

Status: owner-directed constraint, 2026-09-20. Applies to S1Router, S1M and shared contract production source under `packages/*/src`. Source of truth: [owner context](../sources/conversation.md), [DDD boundaries](https://martinfowler.com/bliki/BoundedContext.html), [ports and adapters](https://alistair.cockburn.us/hexagonal-architecture), and [delivery controls](delivery.md). The rules below are project decisions; external sources do not certify compliance.

## Enforceable constraints

CQ-001: every production source file must contain **fewer than 250 physical lines**, including blank lines, comments and docstrings: maximum 249. This conservative definition avoids ambiguous code-line counting. Split by cohesive responsibility before reaching the limit. Do not compress statements, remove useful comments, hide executable code in strings, or rename source files to evade the gate. Generated source has no exemption. Data/model artifacts are separately governed by provenance and size controls. Current runtime language is Python; adopting another language requires extending the gate and recording the decision.

CQ-002: contracts do not import router/model implementations or ML libraries. Router code does not directly import ML libraries. Domain modules import only approved pure standard-library modules, shared contracts or their own domain. Inference modules cannot import training/evaluation/data-preparation workflows. Runtime plugin loading or dynamic imports must not bypass these boundaries. Composition roots and adapters own external dependencies; model training is a separate offline entry point.

`make check` runs `scripts/check_architecture.py`, Ruff, format checking, strict types and behavioral tooling tests. The architecture checker rejects oversized files, direct forbidden imports and relative-import bypasses. These mechanical checks catch specific violations; semantic review is still required for indirect behavior, dependency semantics and SOLID. File length and passing lint do not establish production readiness.

## SOLID review criteria

- Single responsibility: each module/class/function has a cohesive purpose and one main reason to change. Keep admission, routing policy, provider I/O, telemetry and training concerns distinct. Split a file along these seams rather than arbitrary line counts.
- Open/closed: add provider implementations through narrow ports and composition. Do not edit decision policy for each provider. Introduce extension points for demonstrated variation, not hypothetical future providers.
- Liskov substitution: every provider implementing a port must satisfy the same acceptance, failure, timeout/cancellation and provenance contract. Conformance tests must pass for each adapter; fakes must honor the same semantics.
- Interface segregation: callers depend only on operations they use. Keep predict, train, calibrate and artifact management separate; no omnibus model interface or forced unused methods.
- Dependency inversion: domain/application policy depends on contracts/ports, with infrastructure supplied at composition time. Concrete SDKs, filesystem clients and tensor runtimes stay in adapters or model implementation boundaries.

Functions, immutable values and small modules are preferred where sufficient; SOLID does not require a class for every action. Use Strategy/Adapter for real provider variation, a repository abstraction only when persistence variation warrants it, and explicit state transitions for lifecycle behavior. Each introduced pattern must name the requirement and complexity it removes. Avoid service locators, speculative factories, deep inheritance and wrappers that merely rename a call.

## Required review evidence

CQ-003: reviewer records affected requirement IDs, responsibilities, dependency direction, substitutability evidence for changed ports, chosen pattern/rationale (or none), resource/overload impact and tests. Code remains simple, typed and readable; user-facing errors are stable and private. Do not call a refactor scalable without bounded concurrency/backpressure/resource evidence at the appropriate layer.

CQ-004: preserve behavior through meaningful tests and the current layer gate. Coverage thresholds remain unchanged. Requirements are not closed by a size check. NFR targets and operational evidence continue to follow [layered delivery](layered-delivery.md). The current code-quality work is tracked as CHORE-009; this tooling constraint does not change planned R/M implementation status.

## Current verification record — 2026-09-20

Independent reviewer `review_l1_runtime` found no blocking issue in the scoped constraint change. Current largest product file is telemetry at 217 physical lines. Eleven tooling scenarios verify the 249/250 boundary, comments/blanks counting, forbidden absolute and relative imports, valid same-domain imports, and command failure. Admission, pure routing, CLI composition, telemetry and deployment have distinct responsibilities; no new provider port was introduced, so Liskov adapter conformance does not apply to this change. Twenty L1 product tests still pass. S1M has no production implementation yet, so this is enforcement for future model code, not a model-quality claim.

Trace: CQ-001 → `tests/tooling/test_architecture.py::test_physical_line_limit_includes_comments_and_blank_lines`; CQ-002 → parameterized `test_forbidden_imports_fail` and `test_allowed_relative_domain_and_command_errors`; CQ-003 → the independent semantic review above; CQ-004 → `make layer L=1` and [operational evidence](../layers/l1/operations.md).
