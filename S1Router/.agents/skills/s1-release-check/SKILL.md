---
name: s1-release-check
description: Verify S1 product readiness and release evidence without confusing foundation checks with release.
---

# s1-release-check

Read delivery controls and all applicable requirements. Run make check, make ci and, for a requested release check, make release. A missing product suite or missing evidence is a failing gate, not an exemption. Inspect release report underlying files, commands, test lineage, data review, licensing, resource measurements, privacy and rollback drills. Check that quality/resource summaries match real evidence. Reject skipped/xfail requirement tests, missing calibration identities and stale evidence. Report exact failures and remaining actions; do not approve or publish a release on the owner's behalf.

Source of truth: [delivery controls](../../../docs/engineering/delivery.md), [document index](../../../docs/README.md), and [Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Progressive delivery tracking

Use [s1-kanban](../s1-kanban/SKILL.md) for work state and [s1-delivery-loop](../s1-delivery-loop/SKILL.md) for plan through maintenance. Routine reversible local layers are authorized by the owner. Run the scoped layer gate without weakening full-product gates; record actual deployment, observation and maintenance evidence.

## Maintainability constraints

Apply [CQ-001–CQ-004](../../../docs/engineering/code-quality.md): SOLID, maximum 249 physical lines per production source file, cohesive modules and justified patterns. Do not compress/hide code to meet the cap. Run `make architecture`; record semantic review of responsibility, substitution, dependency direction and resource bounds. Mechanical checks do not prove these design properties.
