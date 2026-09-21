"""Pure Python sparse softmax SGD and loss evaluation."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .config import TrainingConfig, TrainingError


def _softmax(logits: Sequence[float]) -> list[float]:
    maximum = max(logits)
    values = [math.exp(value - maximum) for value in logits]
    total = math.fsum(values)
    return [value / total for value in values]


def loss(weights: dict[str, Any], examples: Sequence[tuple[dict[str, float], int]]) -> float:
    if not examples:
        raise TrainingError("validation split must contain at least one labeled example")
    labels = weights["labels"]
    total = 0.0
    for features, target in examples:
        logits = [weights["bias"][index] for index in range(len(labels))]
        for term, count in features.items():
            values = weights["features"].get(term)
            if values is not None:
                for index, value in enumerate(values):
                    logits[index] += value * count
        probability = _softmax(logits)[target]
        total -= math.log(max(probability, 1e-15))
    return total / len(examples)


def update(
    weights: dict[str, Any], examples: Sequence[tuple[dict[str, float], int]], config: TrainingConfig
) -> None:
    if not examples:
        raise TrainingError("train split must contain at least one labeled example")
    width = len(weights["labels"])
    scale = 1.0 / len(examples)
    for features, target in examples:
        logits = [weights["bias"][index] for index in range(width)]
        for term, count in features.items():
            values = weights["features"].get(term)
            if values is not None:
                for index, value in enumerate(values):
                    logits[index] += value * count
        probabilities = _softmax(logits)
        for index in range(width):
            gradient = (probabilities[index] - (1.0 if index == target else 0.0)) * scale
            weights["bias"][index] -= config.learning_rate * gradient
            for term, count in features.items():
                values = weights["features"].get(term)
                if values is not None:
                    values[index] -= config.learning_rate * (
                        gradient * count + config.l2 * values[index]
                    )
