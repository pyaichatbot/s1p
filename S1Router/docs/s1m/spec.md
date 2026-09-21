# S1M — executable behavior specification

Status: proposed full specification, version 0.1, 2026-09-19. MUST requirements define release acceptance, not existing implementation.

S1M produces non-generative typed predictions for registered SDLC tasks and manages the offline lifecycle that makes those predictions auditable. It can run without S1Router; it never chooses a remote fallback. Intent originates in [C1](../sources/conversation.md).

## Normative interface

Implement [decision-v1](../contracts/decision-v1.md) prediction semantics. Capabilities MUST declare artifact identity, contract version, tasks/rubric hashes, languages, precision, runtime, state/head token limits, maximum question count, and maximum choice/score support size.

The initial custom model supports only `sdlc.change_type@1`: English title and body with labels in order bug, feature, documentation, refactor. A supplied question definition must exactly match the registered hash. Arbitrary strings that resemble a known question do not acquire support.

## Requirements

| ID | MUST behavior | Observable acceptance |
| --- | --- | --- |
| M-001 | Version tasks, state schemas, rubrics and exact output support | Renamed/reordered options or altered instructions without new identity are rejected |
| M-002 | Validate dataset provenance, label origin, source rights and schema before training | Missing source/license/review status and invalid labels fail ingestion with example IDs |
| M-003 | Keep train, validation, calibration and final test isolated by group and duplicate lineage | Exact/near-duplicate/template-group overlap and repository/issue leakage fail split validation |
| M-004 | Record a reproducible training configuration and independent baseline comparison | Code, data, environment, seed, optimizer and selected checkpoint digests appear in report |
| M-005 | Return complete finite distributions for supported Choice/Bool/Score heads | Shape, support, normalization, expected-value and P(true) invariants pass property tests |
| M-006 | Reject unsupported tasks/languages and all token/head/option limit overflow before inference | Tokenizer sees complete rendering; no hidden truncation; zero model calls for rejected cases |
| M-007 | Fit calibration only on the calibration split and bind it to complete artifact identity | Modified precision/weights/rubric/preprocessor invalidates calibration; final-test input cannot reach fit |
| M-008 | Evaluate frozen candidates against reviewed independent final data using declared metrics | Report errors/coverage, counts, confidence intervals, slices and baseline comparisons; zero accepts fails |
| M-009 | Export an immutable complete artifact with hashes, licensing and runtime compatibility | Missing/tampered file, traversal path and incompatible contract are rejected |
| M-010 | Install explicitly, run offline, bound runtime resources and support rollback | No inference download/network access; verified prior artifact reloads after failed upgrade |
| M-011 | Treat quantization/export as new candidates requiring recalibration and evaluation | A changed-precision artifact cannot reuse release status or acceptance evidence |
| M-012 | Publish honest model cards and controlled model lifecycle states | Cards describe task envelope, lineage, limitations, data, hardware and measured evidence |
| M-013 | Pass quality/resource release gates on each declared supported runtime | Reference laptop measurements and approved statistical report exist; unsupported lanes are labeled experimental |

## Dataset and task acceptance

A bug restores behavior the issue identifies as broken; a feature adds behavior; documentation changes explanatory material without runtime behavior change; refactor changes implementation without intended behavior change. Mixed/ambiguous examples receive adjudication or exclusion from single-label training, with counts retained. Exclusions cannot be chosen after inspecting final predictions.

Human review policy: all final-test examples independently labeled by two reviewers, disagreements adjudicated with recorded rubric rationale. If only one reviewer is available, the dataset is experimental, not production-release evidence. Synthetic-only testing cannot qualify a release. Publish reviewer agreement and source-group distribution.

Dataset size is evidence-driven: at least 200 locally accepted final questions plus enough total questions and slice coverage to satisfy the error bound. More training examples alone do not prove quality.

## Behavioral scenarios

Given an example from the same issue or duplicate/template cluster appears in train and test, dataset validation fails before any gradient step.

Given a question whose declared labels differ only in order from the registered task, prediction rejects the task hash; the adapter must not silently permute a learned head.

Given input exactly at declared token/head limits, it is accepted if otherwise supported. Adding one token fails explicitly; checking state tokens alone is insufficient.

Given Bool logits [2,0], output includes P(false) and P(true); calibrated confidence in false is not reported as P(true). Given a Score distribution, expected value is the weighted sum of actual level values, not array index.

Given NaN, infinity, missing classes or a sum outside tolerance, the runtime returns a typed inference error. It does not normalize malformed external scores into apparent valid probabilities.

Given a calibrated FP32 artifact is quantized, the quantized bundle begins experimental and automatic acceptance is unavailable until its own calibration/evaluation passes.

Given a failed download, checksum mismatch or incompatible runtime, the currently active bundle remains usable. Given offline inference and a missing checkpoint, fail with artifact_missing; do not fetch it.

Given repeated same-runtime CPU inference with fixed artifact and inputs, probabilities match within absolute tolerance 1e-6 and discrete labels match exactly. Cross-platform comparisons use separately specified numeric tolerances and report differences; training reruns report metric variability, not assumed bitwise equality.

## Evaluation definitions and pass criteria

For each released task/runtime:
- Eligible model-local coverage ≥0.30.
- At least 200 accepted final-test predictions.
- Accepted-error one-sided 95% Clopper–Pearson upper bound ≤0.05; for k errors among n accepts, use Beta inverse CDF at 0.95 with parameters k+1,n-k (k=n gives 1).
- Top-label ECE ≤0.05 with 15 equal-width bins on eligible predictions; report bin counts and uncertainty. This threshold is a project choice, not a universal certificate.
- NLL and multiclass Brier no worse than the held-out majority-probability baseline fitted only on train.
- Report accuracy, macro-F1, all-class confusion matrix, per-source/language/length slices, and calibration before/after. Unsupported slices cannot be hidden in aggregate scores.
- Bool and Score promotion additionally reports task-specific error cost and ordinal/positive-class metrics; current task registry does not authorize automatic high-impact actions.

Comparison uses identical examples and question wording for majority, sparse baseline, Laya, candidate S1M and any available remote model. Include preprocessing differences explicitly. Avoid fitting teacher-generated evaluation labels to the teacher's own preferences.

These requirements adapt [calibration research](https://proceedings.mlr.press/v70/guo17a.html) and [selective prediction](https://arxiv.org/abs/1705.08500); numerical cutoffs are local release decisions.

## Resource protocol

Reference: M1 Pro, 16 GB, OS/Python/library versions recorded, installed bundle, batch=1, concurrency=1, supported task and distribution. Warm up 20 calls, measure 1,000 calls including preprocessing and head inference; warm p95 ≤500 ms. Measure 20 fresh process starts; cold readiness p95 ≤15 s. Complete bundle ≤1 GiB; sampled process-tree RSS peak ≤4 GiB, including workers, with sampling interval and accelerator accounting documented. Report cold/warm separately and disclose caching.

Do not use a T4 benchmark to satisfy the laptop gate. Every additional supported runtime must pass compatibility and quality tests; performance claims require its own report.

## Development and release

CPU tiny-fixture training/inference smoke is part of integration CI. Full training, final-test access, external network comparisons and hardware benchmarks are deliberate experiment/release commands, not every-commit tasks. [PyTorch reproducibility guidance](https://docs.pytorch.org/docs/main/notes/randomness.html) limits what determinism can mean.

No release until [delivery controls](../engineering/delivery.md), M-001 through M-013, artifact audit and operational drills pass. Third-party code and weight licensing are recorded before redistribution; choosing an upstream license does not automatically license our dataset or project.

## Progressive delivery and operational scope

The owner-directed [layered delivery and NFR matrix](../engineering/layered-delivery.md) is part of this product design. Every delivered layer must build, test, deploy locally, observe and maintain its actual capabilities. Full-product readiness is not required to release a clearly scoped local layer; model quality and all future capabilities remain separately gated.

## Mandatory code-quality constraints

Owner-directed [CQ-001–CQ-004](../engineering/code-quality.md) apply to this product: SOLID responsibilities and dependency inversion, narrow substitutable ports, fewer than 250 physical lines per production source file, and justified patterns without speculative abstraction. Mechanical size/import checks run in every local gate; independent semantic review records design rationale and behavioral evidence. Resource bounds and scalability follow the progressive NFR design; a small file alone proves neither. Source decision: [ADR-015](../decisions.md).

## Review clarification for existing helpers (2026-09-21)

The owner deferred FEAT-007/008. Existing data/report helpers are partial infrastructure,
not a completed training/calibration/evaluation pipeline. M-003 must reject cross-split
`group_id` lineage and fail assignment rather than return a leaking partition. M-008
must not fit a baseline on evaluation labels: absent independently frozen predictions,
report the comparison as unavailable. A slice with no accepts has undefined error,
not zero error. Wilson intervals are descriptive and do not satisfy the exact one-sided
release bound above. These corrections do not authorize implementing the deferred layers.
