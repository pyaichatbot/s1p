---
name: s1-spec-change
description: Update S1Router or S1M requirements, contracts and architecture without silent scope drift.
---

# s1-spec-change

Read the affected intent/design/spec, shared contract, source register and ADRs. Identify the owner's requested change versus inferred choices. Trace affected R/M IDs and consumers. Update the normative definition once; preserve IDs unless behavior is removed and documented. Add concrete positive, negative and boundary acceptance scenarios. Update traceability without claiming unimplemented work complete. Review the diff for contradictions and unsupported external claims. Only then refresh the baseline with a meaningful decision reference. Do not automatically rebaseline unexplained changes.

Source of truth: [delivery controls](../../../docs/engineering/delivery.md), [document index](../../../docs/README.md), and [Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Progressive delivery tracking

Use [s1-kanban](../s1-kanban/SKILL.md) for work state and [s1-delivery-loop](../s1-delivery-loop/SKILL.md) for plan through maintenance. Routine reversible local layers are authorized by the owner. Run the scoped layer gate without weakening full-product gates; record actual deployment, observation and maintenance evidence.

## Maintainability constraints

Apply [CQ-001–CQ-004](../../../docs/engineering/code-quality.md): SOLID, maximum 249 physical lines per production source file, cohesive modules and justified patterns. Do not compress/hide code to meet the cap. Run `make architecture`; record semantic review of responsibility, substitution, dependency direction and resource bounds. Mechanical checks do not prove these design properties.
