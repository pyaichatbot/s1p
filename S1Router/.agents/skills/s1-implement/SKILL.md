---
name: s1-implement
description: Implement an approved S1Router or S1M requirement with behavioral evidence.
---

# s1-implement

Read the relevant spec and contract and name the requirement IDs before editing. Implement one vertical slice within assigned module ownership. Add a behavioral test with requirement and behavioral markers; run it to observe the intended failure before changing product behavior. Use deterministic fakes for clocks/providers, plus real adapter conformance fixtures. Keep domain code independent of I/O and tensor dependencies. Add actual code paths and pytest node IDs to traceability after tests pass. Run make ci and explain any remaining planned requirements. Do not skip tests or change thresholds to pass.

Source of truth: [delivery controls](../../../docs/engineering/delivery.md), [document index](../../../docs/README.md), and [Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Progressive delivery tracking

Use [s1-kanban](../s1-kanban/SKILL.md) for work state and [s1-delivery-loop](../s1-delivery-loop/SKILL.md) for plan through maintenance. Routine reversible local layers are authorized by the owner. Run the scoped layer gate without weakening full-product gates; record actual deployment, observation and maintenance evidence.

## Maintainability constraints

Apply [CQ-001–CQ-004](../../../docs/engineering/code-quality.md): SOLID, maximum 249 physical lines per production source file, cohesive modules and justified patterns. Do not compress/hide code to meet the cap. Run `make architecture`; record semantic review of responsibility, substitution, dependency direction and resource bounds. Mechanical checks do not prove these design properties.
