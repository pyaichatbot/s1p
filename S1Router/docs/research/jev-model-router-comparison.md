# Jev model-router template comparison

Reviewed 2026-09-20 at commit `73fdf20e1c2548e438c37d31ad5ece5179298f58` (upstream commit timestamp 2026-09-20T03:10:52Z). Source: [pinned directory](https://github.com/davila7/claude-code-templates/tree/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router). The requested Luna/high follow-up hit a usage limit; the root agent completed read-only source inspection. No upstream code was installed or executed, and no upstream tests were run.

## Actual scope

This is a Claude Code host integration that selects a model tier and reasoning effort. It asks about task tier, effort and execution risk using TypeSafe or Vercel; a host classifier is the fallback. Main-model switching defaults off, while main effort and subagent-model routing default on. It is neither a local trained System One checkpoint nor a general standalone policy engine. Host compatibility is an upstream claim, not verified here. [README](https://github.com/davila7/claude-code-templates/blob/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router/README.md)

Pure policy is separated from host I/O. Upgrade and downgrade thresholds differ; missing confidence prevents known downgrades, and risk can force escalation. Unknown current models are treated as upgrade-direction changes. The parser accepts provider confidence or maximum reported probability without full S1 distribution/calibration validation. [Policy source](https://github.com/davila7/claude-code-templates/blob/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router/hooks/policy.ts)

Hooks classify on prompt submission, reuse a decision within a turn, and route subagent creation. Remote HTTP races a timer; the source does not cancel the losing fetch. The built-in classifier path has no corresponding timeout race. Outbound state includes prompt text and, for subagents, description/type. Caught errors are logged as strings. The source delegates built-in classification to the host, so the README's offline implication cannot be established from this directory alone. [Hook implementation](https://github.com/davila7/claude-code-templates/blob/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router/hooks/jev-model-router.ts)

Source tests cover threshold direction, numeric effort preservation, risk floors, optional confidence, protocol shapes, ambiguous queued prompts, model aliases and logging. These are useful scenario references; inspection is not an executed conformance result. [Tests](https://github.com/davila7/claude-code-templates/blob/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router/tests/policy.test.ts)

## Fit and decisions for S1

The following are project recommendations derived from that inspection, not upstream capabilities:

| S1 boundary | Reuse or required difference |
| --- | --- |
| R-003/R-004: prediction versus policy | Reuse separate decision and policy stages. Confidence bars remain task-specific calibrated acceptance policies; provider labels or maximum probability alone do not authorize automatic acceptance. |
| R-006/R-007/R-008: failure, deadlines and cost | Add cancellation settlement, bounded in-flight work, request budgets and canonical per-question outcomes. Retaining a host's original request is a consumer fallback, not evidence that S1 answered successfully. |
| R-009/R-010: privacy and provenance | Enforce explicit outbound permission, allowed endpoint, data class, redaction and immutable task/model/policy identity before sending state. Sanitize errors; do not copy raw provider error strings. A missing external key does not prove offline execution. |
| R-011: host integration | Treat model/effort selection as a later consumer adapter with explicit host capabilities, user-selected model constraints and turn identity. Separate classification from applying a change; do not mutate our Codex agent configuration from a prediction. |
| M-003/M-008: model evidence | The template supplies no local checkpoint, calibration fit, isolated final-test evidence or S1M training lifecycle. S1M remains independently required. |
| CQ-001/CQ-003: maintainability | Preserve pure policy/I/O separation, but split request encoding, answer validation, routing policy and host orchestration into cohesive modules if reused. The inspected policy and hook files have 504 and 327 physical lines, exceeding our 249-line cap. |

The upstream repository is [MIT licensed](https://github.com/davila7/claude-code-templates/blob/73fdf20e1c2548e438c37d31ad5ece5179298f58/LICENSE). License obligations and dependency/provider terms still require review before copying code. No dependency is added by this research.

Source of truth for our decisions: [decision contract](../contracts/decision-v1.md), [router design](../s1router/design.md), [model design](../s1m/design.md), [code quality](../engineering/code-quality.md), and [ADR-016](../decisions.md). This is a useful host-adapter reference for a later layer, not a replacement for either product or permission to install the mod.
