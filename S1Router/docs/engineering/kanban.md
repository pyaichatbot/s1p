# Repository Kanban contract

Source of truth: [owner direction](../sources/conversation.md), [layered delivery](layered-delivery.md), and [AI-native lifecycle](https://claude.com/blog/the-ai-native-sdlc-playbook). These controls are repository design choices, not claims that the article prescribes this schema.

`kanban/board.json` is canonical; `kanban/index.html` is a generated, offline, read-only dashboard. Agents use `node scripts/kanban.mjs`; they never edit either file manually. No service, database or account is needed. Node 22 is the supported runtime; there are no npm dependencies.

## Behaviors

- KB-001: create FEAT, BUG, CHORE or SPIKE items with stable monotonic IDs, title, requirement references and history. Scope/title updates require a recorded rationale. Reject malformed arguments without changing the board.
- KB-002: move backlog → ready → in_progress → review → done. Active work needs an owner. Any nonterminal state may block with a reason; blocked work resumes through ready. Review can return to in_progress; done can reopen to ready with a reason. Dependencies must be done before work starts.
- KB-003: record lifecycle stages plan/design/build/test/deploy/observe/maintain separately from status. Done requires all stages, a review note, and at least one existing repo-local evidence file with its SHA-256 digest. A stage may be recorded as not applicable only with an explicit rationale in its note. Evidence is traceability, not automatic proof of correctness or owner approval.
- KB-004: serialize mutations with an exclusive lock; optional expected revision prevents stale writes. Atomic JSON replacement prevents partial canonical state. HTML is regenerated after every mutation; if generation fails, JSON remains canonical and `render` repairs the view. Never silently remove a lock; verify its owning process before manual recovery.
- KB-005: escape all card content, use no remote assets or executable user content, provide search and status columns. Dashboard never sends data externally. Limit board input to 2 MiB and 2,000 cards; archive policy is a later explicit change.

## Commands

```sh
node scripts/kanban.mjs create --type FEAT --title 'Local runtime' --requirements L1-001,L1-005
node scripts/kanban.mjs assign FEAT-001 --owner router-engineer
node scripts/kanban.mjs update FEAT-001 --requirements L1-001,L1-005 --note 'Reviewed scope clarification'
node scripts/kanban.mjs move FEAT-001 --status ready
node scripts/kanban.mjs move FEAT-001 --status in_progress --expect-revision 3
node scripts/kanban.mjs stage FEAT-001 --stage build --note 'Behavioral tests fail before implementation'
node scripts/kanban.mjs evidence FEAT-001 --path docs/layers/l1/operations.md --note 'Deployment and observation record'
node scripts/kanban.mjs move FEAT-001 --status review
node scripts/kanban.mjs move FEAT-001 --status done --note 'Reviewed against L1 acceptance and passing gate evidence'
node scripts/kanban.mjs list
node scripts/kanban.mjs validate
node scripts/kanban.mjs render
```

Use `--root /absolute/repo` for isolated test boards or another explicitly selected checkout. To replace changed evidence, reopen completed work first, then use `evidence ID --path FILE --note "Reviewed change and rerun rationale" --replace true`. The previous hash remains in history; validation rejects drift until explicitly reviewed and replaced. Each command emits JSON or a concise error and nonzero exit. Stage notes describe actual work; do not invent deployment for documentation changes. Requirement references link scope, while `docs/traceability.json` remains authoritative for implementation acceptance. `make check` runs Node syntax validation, the board validator and behavioral tests with at least 90% line and 85% branch coverage for the CLI. Completion claims still need the applicable layer/product gate.
