"""Offline sparse training; this package is never imported by inference."""

from .baseline import MajorityBaseline
from .config import TrainingConfig, TrainingError
from .trainer import EpochMetrics, TrainingRun, train_sparse_model

__all__ = [
    "EpochMetrics",
    "MajorityBaseline",
    "TrainingConfig",
    "TrainingError",
    "TrainingRun",
    "train_sparse_model",
]
