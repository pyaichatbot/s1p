---
name: s1-model-evaluation
description: Run or review S1M dataset, calibration and model evaluation experiments.
---

# s1-model-evaluation

Read the model spec and exact task/artifact manifest. Validate licenses, reviewed label origin, split group isolation and immutable IDs before fitting. Use train for gradients, validation for tuning, calibration for calibration/thresholds, and untouched test for frozen evaluation. Record all artifact identities, commands, seeds, environment, metrics and slice counts. Compute accepted error/coverage with the required statistical bound. Measure deployed precision on declared hardware; quantization creates a new candidate. Synthetic labels are not independent ground truth. Never claim teacher agreement as real-world accuracy or T4 latency as laptop latency.

Source of truth: [delivery controls](../../../docs/engineering/delivery.md), [document index](../../../docs/README.md), and [Codex skills](https://learn.chatgpt.com/docs/build-skills).

## Progressive delivery tracking

Use [s1-kanban](../s1-kanban/SKILL.md) for work state and [s1-delivery-loop](../s1-delivery-loop/SKILL.md) for plan through maintenance. Routine reversible local layers are authorized by the owner. Run the scoped layer gate without weakening full-product gates; record actual deployment, observation and maintenance evidence.
