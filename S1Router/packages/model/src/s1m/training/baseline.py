"""Independent train-fitted majority baseline for validation comparison."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from s1m.data.split import SplitRole
from s1m.data.validation import Record

from .config import TrainingConfig, TrainingError


@dataclass(frozen=True, slots=True)
class MajorityBaseline:
    majority_label: str
    train_counts: dict[str, int]
    validation_count: int
    correct: int
    accuracy: float
    fitted_split: SplitRole = SplitRole.TRAIN
    measured_split: SplitRole = SplitRole.VALIDATION


def fit_majority(
    train: Sequence[Record], validation: Sequence[Record], config: TrainingConfig
) -> MajorityBaseline:
    counts = Counter(record.label for record in train)
    if not counts or any(label not in config.labels for label in counts):
        raise TrainingError("train labels must be present and supported")
    majority = min(counts, key=lambda label: (-counts[label], label))
    correct = sum(record.label == majority for record in validation)
    return MajorityBaseline(
        majority_label=majority,
        train_counts=dict(counts),
        validation_count=len(validation),
        correct=correct,
        accuracy=correct / len(validation),
    )
