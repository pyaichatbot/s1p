---
name: s1-kanban
description: Create, claim, update and complete repository FEAT, BUG, CHORE and SPIKE work through the evidence-backed local Kanban CLI.
---

# S1 Kanban workflow

Read [board contract](../../../docs/engineering/kanban.md) and use `node scripts/kanban.mjs list` before creating work. Reuse an existing item for the same scope. Canonical JSON and HTML are generated only through this CLI.

1. Create a bounded item with type, title and requirement IDs. Split unrelated changes. Describe source decisions in the plan stage note.
2. Assign an owner, move backlog → ready → in_progress. Use `--expect-revision` from the latest read when multiple agents work. On contention, reread and reconcile; never delete a live lock. Dependencies must be Done before starting.
3. Record plan/design/build/test/deploy/observe/maintain stages as actual evidence becomes available. Explain explicitly when a stage is not applicable. Update the board on meaningful state changes, not after every tool call.
4. On a blocker, move to blocked with a concrete reason and next action; return through ready once resolved. New operational defects become BUG items linked to the original requirement and sanitized incident record.
5. Attach bounded repository evidence with `evidence ID --path FILE --note TEXT`. Never include secrets or raw customer state. Evidence hashes detect drift. Replace changed evidence only with reviewed rationale and `--replace true`; completed work must be reopened first. Preserve the former hash in history.
6. Move to review after applicable gates pass. Record reviewer findings and resolutions. Done requires all lifecycle stage notes, evidence and a review note. A Done scoped item does not imply full-product release. Do not invent approval, passing tests or ML measurements.
7. Run `node scripts/kanban.mjs validate` and `make check`; use `make layer L=1` or `make ci` for product scope. Open kanban/index.html for the owner when useful. HTML is read-only; changes use the CLI then reload.

Source of truth: [delivery controls](../../../docs/engineering/delivery.md), [Kanban contract and commands](../../../docs/engineering/kanban.md), [owner direction](../../../docs/sources/conversation.md).
