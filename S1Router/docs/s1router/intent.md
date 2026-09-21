# S1Router — intent

Status: proposed full product intent, version 0.1, 2026-09-19.

## Purpose

S1Router is a local-first decision runtime for software-development workflows. Given state and typed questions, it chooses a permitted deterministic rule, a supported local or hosted System One provider, an explicitly enabled System Two provider, or human review. It returns a decision record; the calling application decides how to act. This follows the user's SDLC integration and independent-router goals in [C1](../sources/conversation.md).

The product value is measured reduction in remote decision calls while maintaining an explicit accepted-error bound. Merely wrapping a gateway, printing confidence, or adding a small model does not establish that value.

## Users and jobs

- A CLI user classifies a short issue offline and sees the result, source, and reason for any abstention.
- An SDLC integrator asks several independent bounded questions and consumes stable JSON, without knowing which backend answered.
- A policy owner defines permitted providers, data handling, support envelopes, latency/cost limits, and acceptance criteria.
- A maintainer replays a problematic decision with its exact policy and artifact versions and can disable an unhealthy provider.
- An enterprise operator connects an approved gateway without changing application semantics.

Tetrate is a potential provider-access layer beneath this runtime. Compatibility is tested against the deployment actually used, rather than inferred from branding. [G1](https://docs.tetrate.ai/product-architecture/architecture-overview/)

## Outcomes and product boundaries

The full product includes a Python SDK, JSON CLI, versioned typed contract, deterministic rule evaluation, provider adapters, task support checks, calibrated acceptance, per-question abstention, privacy/budget enforcement, bounded concurrency, audit records, replay, model installation integration, and offline evaluation.

It does not execute tools, merge code, waive required reviews, make financial transactions, train models in response to requests, replace a gateway, or promise universal question answering. A caller must not interpret a recommendation as an authorization. Security-review predictions may recommend additional review; automated review exemptions are excluded from this baseline.

S1M is an optional producer of predictions and model capability metadata. S1Router must remain usable with a fake provider, rules, or another contract-conforming implementation when S1M is absent.

## Acceptance of value

Proposed release targets for the initial English issue-classification workload:

| Outcome | Target/evidence |
| --- | --- |
| Safe local acceptance | Final-test one-sided 95% upper confidence bound on model-accepted error ≤5% |
| Useful local coverage | At least 30% of eligible held-out questions accepted by the local model; separately report rules and total-local rates |
| Operational overhead | Warm router-only p95 ≤10 ms over 10,000 fake-provider calls on documented M1 Pro 16 GB conditions |
| Local privacy | Offline mode causes zero outbound calls, including telemetry and lazy downloads |
| Predictable failures | Each question has a terminal answer, review-needed result, or typed error; no fabricated probability |
| Integration | Same serialized contract works in CLI, SDK, and adapter conformance tests |

Risk and coverage are assessed together, following selective-classification methodology; thresholds above are our product choices. [M4](https://arxiv.org/abs/1705.08500)

## Pragmatic approach and delivery

Build one traceable vertical slice before expanding tasks. Keep domain decisions pure, inputs explicit, dependencies replaceable, and external I/O behind adapters. These are project applications of [pragmatic programming](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) and [ports/adapters](https://alistair.cockburn.us/hexagonal-architecture), not claims that any methodology guarantees AI output.

The first milestone is a credible demo with evidence and abstention. The full release is gated by the [specification](spec.md) and [delivery controls](../engineering/delivery.md). A demonstration on 50–200 examples is exploratory; it does not replace a sufficiently sized independent release test.

## Assumptions and source of truth

Python-first packaging, English initial tasks, single-user local operation, and numeric targets are proposed choices. Public/synthetic appropriately licensed data is the initial evidence base; employer systems are separate future integration work. The [spec](spec.md) owns required behavior, [design](design.md) owns boundaries, and [decision contract](../contracts/decision-v1.md) owns interchange semantics. [Source register](../sources/README.md) records provenance.

## Progressive delivery and operational scope

The owner-directed [layered delivery and NFR matrix](../engineering/layered-delivery.md) is part of this product design. Every delivered layer must build, test, deploy locally, observe and maintain its actual capabilities. Full-product readiness is not required to release a clearly scoped local layer; model quality and all future capabilities remain separately gated.
