# S1M — intent

Status: proposed full product intent, version 0.1, 2026-09-19.

## Purpose

S1M is a small, locally deployable System One model and its reproducible lifecycle for bounded software-development decisions. It accepts a state plus registered typed questions and returns distributions over known labels or ordinal levels. It does not generate explanations, choose remote providers, execute tools, or decide whether its own prediction is permitted to drive a workflow.

The user's goals are learning model engineering, creating a credible SDLC-specialized artifact, and integrating local intelligence with an existing CLI on a personal M1 Pro with 16 GB memory. S1M is independently useful through its inference API; S1Router can consume it as one replaceable provider. [C1](../sources/conversation.md)

## Meaning of “our System One model”

Three artifact identities must remain distinct:

1. An unchanged external checkpoint integrated through an adapter: label it “S1Router with a Laya backend.”
2. An externally initialized checkpoint fine-tuned on reviewed SDLC data: label it “S1M SDLC specialization,” preserving upstream lineage.
3. A trained decision head/backbone experiment: describe the actual architecture and training, without claiming a new foundation model or proprietary Jev reproduction.

Laya provides a concrete non-generative typed-decision baseline. Its published variants, limitations, and comparisons motivate evaluation, not adoption without measurement. [M1](https://github.com/NandhaKishorM/laya), [M2](https://huggingface.co/convaiinnovations/laya)

## Users and scope

An ML developer ingests licensed examples, creates leakage-resistant splits, trains a small encoder/head, calibrates distributions, compares baselines, exports an immutable bundle, and documents limitations. A CLI user installs a verified bundle separately from application code and runs supported decisions offline. A model reviewer checks labels, split lineage, calibration, supported domain, resource measurements, and release evidence.

The full scope includes dataset schema and provenance, reviewed task rubrics, split manifests, sparse and pretrained baselines, training recipes, typed heads, calibration, selective evaluation, quantization experiments, inference packaging, checksums, model cards, compatibility declarations, and rollback-ready immutable artifacts.

The initial task is English issue classification into bug/feature/documentation/refactor. The API includes Bool and ordinal Score from the outset, but no checkpoint claims support for those tasks until corresponding datasets and release evidence exist. Later tasks include workflow recommendation and complexity scoring. Review-required flags may add review, never waive mandatory review under this baseline.

## Measurable outcomes

Proposed targets, to be demonstrated on the M1 Pro 16 GB reference machine:

| Property | Proposed requirement |
| --- | --- |
| Automatic issue classification | Model-accepted error one-sided 95% upper bound ≤5%, at ≥30% eligible-question coverage and ≥200 accepted test questions |
| Artifact footprint | Complete selected lite bundle ≤1 GiB, including tokenizer/head/calibration metadata |
| Runtime peak | Peak process-tree resident memory ≤4 GiB, with measurement method disclosed |
| Warm latency | p95 ≤500 ms for one supported question, batch size one |
| Cold startup | p95 ≤15 seconds to verified readiness from an already installed bundle |
| Privacy | Fully offline installed inference; no implicit downloads or telemetry |
| Provenance | Every released prediction binds exact weights, tokenizer, preprocessing, rubric and calibration |
| Honesty | Zero fabricated benchmark results; unreleased/failed experiments remain visibly experimental |

These resource ceilings are deliberately more realistic than the conversation's speculative memory estimates. They are project release targets, not established Laya or Apple performance. If a candidate fails, keep it experimental or propose a revised profile through the decision process.

## Why calibration and data quality are central

The core product is reliable bounded prediction under a documented distribution. A small model that confidently misclassifies unseen cases cannot be repaired by a router threshold alone. Training, tuning, calibration and final testing need separate data roles; calibrated risk must be measured at the actual acceptance threshold. [M3](https://proceedings.mlr.press/v70/guo17a.html), [M4](https://arxiv.org/abs/1705.08500)

Synthetic data is useful for pipeline development and augmentation but cannot be the only release-test truth. Teacher outputs remain teacher labels until reviewed. No employer data or paid compute is assumed available.

## Delivery and source of truth

First establish baseline inference and evaluation, then compare a custom specialization on the same frozen test distribution. Model training need not block S1Router's first working slice. Release is conditional on evidence; producing weights alone is not success.

The [specification](spec.md) owns acceptance, [design](design.md) owns the model lifecycle, and [decision contract](../contracts/decision-v1.md) defines standalone inference semantics. The [source register](../sources/README.md) distinguishes primary evidence from project choices.

## Progressive delivery and operational scope

The owner-directed [layered delivery and NFR matrix](../engineering/layered-delivery.md) is part of this product design. Every delivered layer must build, test, deploy locally, observe and maintain its actual capabilities. Full-product readiness is not required to release a clearly scoped local layer; model quality and all future capabilities remain separately gated.
