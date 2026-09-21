---
name: s1-delivery-loop
description: Deliver a scoped S1 layer through plan, design, build, test, local deployment, observation and maintenance with evidence and no specification drift.
---

# S1 delivery loop

Use the owner's chosen iterative approach. Read the relevant standalone intent/design/spec, shared contract, [layered delivery](../../../docs/engineering/layered-delivery.md) and [Kanban contract](../../../docs/engineering/kanban.md). Select one bounded vertical slice; avoid adding services or abstraction layers without a current requirement.

- Plan: create or claim a Kanban item; identify requirement IDs, acceptance scenarios, constraints and source decisions. Separate measured facts from targets.
- Design: assign domain ownership and failure behavior; cover privacy, deadlines, resource limits, overload, observability and recovery at the current layer. Update normative docs before behavior changes. Review semantic consistency before baseline refresh.
- Build/test: follow s1-implement; observe a failing behavioral test, implement the smallest change, and run the relevant locked local gates. Pure domain tests use fake time/providers. No skipping, weakened thresholds or fabricated mappings.
- Deploy: run the scoped gate, verify the artifact, activate locally and retain rollback evidence. Routine reversible local deployment is already authorized. External publication, paid compute or credential-sensitive expansion follows the user's actual scope.
- Observe: run local health, smoke and bounded redacted observation. Insufficient traffic is insufficient evidence, never healthy production SLO proof. Report corruption and missing signals.
- Maintain: capture defects as requirement-linked BUGs, reproduce with a regression, repair, redeploy and observe again. For a clean run, record findings, limitations and follow-up. Do not create a scheduled monitor unless the user requests one.
- Review/complete: use an independent reviewer when delegation is authorized or required by the active workflow; resolve findings before completion. Record reviewer identity and exact commands. Close only verified scope. Full-product readiness stays blocked until all product and release evidence passes.

Sources: [owner direction](../../../docs/sources/conversation.md), [delivery policy](../../../docs/engineering/delivery.md), [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook). Concrete gates and layering are this repository's engineering decisions.

## Maintainability constraints

Apply [CQ-001–CQ-004](../../../docs/engineering/code-quality.md): SOLID, maximum 249 physical lines per production source file, cohesive modules and justified patterns. Do not compress/hide code to meet the cap. Run `make architecture`; record semantic review of responsibility, substitution, dependency direction and resource bounds. Mechanical checks do not prove these design properties.
