# Source register

Reviewed: 2026-09-19. Links are source locations, not pinned implementation dependencies. Before using third-party code or weights, resolve an immutable revision and record checksums and license evidence in the artifact manifest.

| ID | Primary source | What it supports and limits |
| --- | --- | --- |
| C1 | [Conversation synthesis](conversation.md) | Full accessible branch and present user intent; previous assistant recommendations remain hypotheses |
| D1 | [Fowler: Bounded Context](https://martinfowler.com/bliki/BoundedContext.html) | Separate domain models and explicit context relationships |
| D2 | [Cockburn: Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture) | Ports/adapters and testing application behavior independently of external devices |
| P2 | [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook) | Owner-selected lifecycle approach; see local adoption and NFR decisions in engineering/layered-delivery.md |
| P1 | [Thomas and Hunt: The Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) | General pragmatic engineering inspiration; the AI workflow in this repository is our own operational interpretation |
| M1 | [Laya repository](https://github.com/NandhaKishorM/laya) | Typed non-generative baseline, checkpoint differences, limits, author-reported benchmarks |
| M2 | [Laya model card](https://huggingface.co/convaiinnovations/laya) | Artifact family and metadata; not proof of suitability for SDLC |
| M3 | [Guo et al., calibration, ICML 2017](https://proceedings.mlr.press/v70/guo17a.html) | Held-out post-hoc temperature calibration methodology |
| M4 | [Geifman and El-Yaniv, selective classification](https://arxiv.org/abs/1705.08500) | Risk/coverage framing for abstaining classifiers |
| M5 | [PyTorch reproducibility](https://docs.pytorch.org/docs/main/notes/randomness.html) | Seeds and deterministic settings have platform/version limitations |
| G1 | [Tetrate architecture](https://docs.tetrate.ai/product-architecture/architecture-overview/) | Gateway boundary and provider access; actual enterprise endpoint compatibility remains unverified |
| A1 | [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | Repository instruction discovery |
| A2 | [Codex custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Project agent TOML fields and inheritance |
| A3 | [Codex skills](https://learn.chatgpt.com/docs/build-skills) | SKILL.md metadata and .agents/skills discovery |
| Q1 | [uv locking/sync](https://docs.astral.sh/uv/concepts/projects/sync/) | Locked dependency workflow |
| Q2 | [Ruff](https://docs.astral.sh/ruff/) | Python lint/format tooling |
| Q3 | [pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html) | Registered markers and strict marker validation |
| Q4 | [Coverage.py branch coverage](https://coverage.readthedocs.io/en/latest/branch.html) | Measuring branch execution; coverage does not prove correctness |
| Q5 | [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) | Lifecycle risk and evidence framing; no certification implied |

## Claims policy

A source-backed fact cites its source at the point of use. An engineering choice is labeled as a project decision. A numeric target is labeled as a target. A result must link a reproducible report, immutable inputs, environment, and command.

Do not reproduce historical benchmark tables as project results. Laya's repository currently lists multiple checkpoint variants and acknowledges that its Jev comparison uses third-party results with different prompts/sample sizes. This is enough to motivate a baseline experiment, not a superiority claim. [M1](https://github.com/NandhaKishorM/laya)

The X URL in C1 was context only; its contents were not independently retrieved. Hidden historical citation indices cannot be resolved from the thread and are not references here. Exact Laya revision, model weights, enterprise credentials, final redistribution license choice, and production measurements remain release evidence to acquire, not placeholders to silently fill.

## Additional pinned research — 2026-09-20

- JEV-LOCAL: [LocalJev 3f23e36](https://github.com/githubnext/localjev/tree/3f23e36e1a3bff46c7e83e8e3781d3512bc82021), MIT source. A prompted-probability bridge and screening harness; not S1 calibration or release evidence.
- JEV-ALIGN: [jev-align 49753df](https://github.com/sutro-sh/jev-align/tree/49753df924d30c0d3642b58e0b9b1e89921dc102), Apache-2.0 source. Interactive annotation and prompt optimization reference; data/model/provider rights are separate.

Detailed source-level qualifications and immutable citations: [comparison](../research/jev-projects-comparison.md).

- JEV-HOST: [jev-model-router at 73fdf20](https://github.com/davila7/claude-code-templates/tree/73fdf20e1c2548e438c37d31ad5ece5179298f58/cli-tool/components/mods/productivity/jev-model-router), read 2026-09-20; repository MIT license. Claude Code model/effort host integration reference, with unverified host compatibility and no S1M checkpoint or calibration evidence. [Source comparison](../research/jev-model-router-comparison.md).
