"""Validated, bounded configuration for the offline sparse trainer."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


class TrainingError(ValueError):
    """Raised when training inputs or configuration violate the offline contract."""


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Small standard-library training configuration with explicit resource bounds."""

    labels: tuple[str, ...] = ("bug", "feature", "documentation", "refactor")
    seed: int = 0
    epochs: int = 20
    learning_rate: float = 0.1
    l2: float = 0.0
    vocabulary_size: int = 10_000
    max_records: int = 100_000
    max_text_chars: int = 20_000

    def __post_init__(self) -> None:
        if not self.labels or len(set(self.labels)) != len(self.labels):
            raise TrainingError("labels must be non-empty and unique")
        if any(not isinstance(label, str) or not label for label in self.labels):
            raise TrainingError("labels must be non-empty strings")
        if type(self.seed) is not int:
            raise TrainingError("seed must be an integer")
        if not 1 <= self.epochs <= 1000:
            raise TrainingError("epochs exceeds supported bound")
        if not math.isfinite(self.learning_rate) or not 0 < self.learning_rate <= 10:
            raise TrainingError("learning_rate exceeds supported bound")
        if not math.isfinite(self.l2) or not 0 <= self.l2 <= 10:
            raise TrainingError("l2 exceeds supported bound")
        if not 1 <= self.vocabulary_size <= 10_000:
            raise TrainingError("vocabulary_size exceeds supported bound")
        if not 1 <= self.max_records <= 100_000:
            raise TrainingError("max_records exceeds supported bound")
        if not 1 <= self.max_text_chars <= 1_000_000:
            raise TrainingError("max_text_chars exceeds supported bound")

    def canonical_json(self) -> str:
        return json.dumps(
            {
                "labels": self.labels,
                "seed": self.seed,
                "epochs": self.epochs,
                "learning_rate": self.learning_rate,
                "l2": self.l2,
                "vocabulary_size": self.vocabulary_size,
                "max_records": self.max_records,
                "max_text_chars": self.max_text_chars,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
