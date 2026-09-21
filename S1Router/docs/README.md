# S1Router and S1M documentation

Status: proposed architecture baseline, 2026-09-19. This repository follows a progressive local delivery loop. Layer-specific releases are verified independently; full-product/model readiness remains evidence-gated.

## Product documents

| Product | Purpose | Architecture | Verifiable requirements |
| --- | --- | --- | --- |
| S1Router | [intent](s1router/intent.md) | [design](s1router/design.md) | [spec](s1router/spec.md) |
| S1M | [intent](s1m/intent.md) | [design](s1m/design.md) | [spec](s1m/spec.md) |

Each document explains its product independently. The shared wire format is defined once in [decision contract](contracts/decision-v1.md); copying either product's document set also requires that linked contract, the source register, and delivery controls for implementation.

## Source of truth

1. Explicit owner decisions recorded in this repository supersede assumptions.
2. Product `spec.md` files define required behavior, identified by stable requirement IDs.
3. [Decision contract](contracts/decision-v1.md) owns shared field semantics; change both consumers together.
4. Product `design.md` files explain implementation boundaries; `intent.md` files explain outcomes and scope.
5. [Delivery controls](engineering/delivery.md), [traceability](traceability.json), and executable local checks enforce the implementation workflow.
6. External sources explain evidence and methods; they do not silently change product requirements.

A contradiction must be resolved explicitly in [decisions](decisions.md), never by quietly choosing whichever file is convenient. All numeric release thresholds in these documents are proposed project requirements, not published model performance. The owner has directed continuous progressive implementation and local deployment; routine layer work proceeds within that scope.

## Start here

Read [conversation synthesis](sources/conversation.md), [source register](sources/README.md), and [decisions](decisions.md). Then read the appropriate product set.

Run `make bootstrap` once to install locked development tools, then `make check`. The foundation gate checks documentation and its own tooling. Use `make layer L=1` for the first runnable layer; see [layered delivery](engineering/layered-delivery.md) and [L1 plan](layers/l1/plan.md). `make ci` is the product gate and deliberately fails until product code and requirement-linked tests exist. `make release` additionally requires reviewed model and operational evidence.

Sources: [current request and conversation](sources/conversation.md), [Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Delivery board and research

Use [Kanban commands](engineering/kanban.md) to maintain the repository's `kanban/board.json` and `kanban/index.html`. Agents use the s1-kanban and s1-delivery-loop skills; coordinator/verifier roles keep scope and evidence explicit. The dashboard is a read-only local view with search and expandable work records.

Read [LocalJev/jev-align comparison](research/jev-projects-comparison.md) for the requested Luna/high research. Adopted boundaries are recorded in [ADR-014](decisions.md).

[Code-quality contract](engineering/code-quality.md) enforces the owner's SOLID and file-size constraints alongside semantic review. Run `make architecture` for a focused check.

The additional [Jev model-router template review](research/jev-model-router-comparison.md) records host-integration lessons and gaps. Luna's follow-up was usage-limited; the root agent completed the pinned source review.
