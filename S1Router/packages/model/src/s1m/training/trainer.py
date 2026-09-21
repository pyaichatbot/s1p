"""Offline sparse multiclass training and validation checkpoint selection."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import platform
import sys
from dataclasses import dataclass
from typing import Any, Sequence

from s1m.data.split import SplitRole, SplitLeakageError, validate_splits
from s1m.data.validation import Record
from s1m.reporting.training_report import TrainingReport, build_training_report

from .baseline import MajorityBaseline, fit_majority
from .config import TrainingConfig, TrainingError
from .features import data_digest, vector, vocabulary
from .optimizer import loss, update


@dataclass(frozen=True, slots=True)
class EpochMetrics:
    epoch: int
    train_loss: float
    validation_loss: float
    checkpoint_digest: str


@dataclass(frozen=True, slots=True)
class TrainingRun:
    weights: dict[str, Any]
    config_digest: str
    data_digest: str
    checkpoint_digest: str
    selected_epoch: int
    history: tuple[EpochMetrics, ...]
    train_count: int
    validation_count: int
    excluded_counts: dict[str, int]
    baseline: MajorityBaseline
    report: TrainingReport


def _validate_records(records: Sequence[Record], config: TrainingConfig) -> None:
    if not records or len(records) > config.max_records:
        raise TrainingError("record count exceeds bound or is empty")
    try:
        validate_splits(list(records))
    except SplitLeakageError as exc:
        raise TrainingError(str(exc)) from exc
    ids = [record.example_id for record in records]
    if len(ids) != len(set(ids)):
        raise TrainingError("duplicate example_id across split roles")
    if any(record.split is None for record in records):
        raise TrainingError("every record must declare a split role")
    allowed = {role.value for role in SplitRole}
    if any(str(record.split) not in allowed for record in records):
        raise TrainingError("unknown split role")


def _partition(records: Sequence[Record]) -> tuple[list[Record], list[Record], dict[str, int]]:
    train = [record for record in records if record.split == SplitRole.TRAIN]
    validation = [record for record in records if record.split == SplitRole.VALIDATION]
    excluded = {
        role.value: sum(record.split == role for record in records)
        for role in (SplitRole.CALIBRATION, SplitRole.FINAL_TEST)
    }
    if not train or not validation:
        raise TrainingError("training requires non-empty train and validation splits")
    return train, validation, excluded


def _labeled_examples(
    records: Sequence[Record], config: TrainingConfig, terms: set[str]
) -> list[tuple[dict[str, float], int]]:
    index = {label: number for number, label in enumerate(config.labels)}
    result: list[tuple[dict[str, float], int]] = []
    for record in records:
        if record.label not in index:
            raise TrainingError(f"{record.example_id}: unsupported or missing label")
        result.append((vector(record, config, terms), index[record.label]))
    return result


def _weights(config: TrainingConfig, terms: Sequence[str]) -> dict[str, Any]:
    return {
        "format": "s1m.sparse-linear.v1",
        "labels": list(config.labels),
        "bias": [0.0 for _ in config.labels],
        "features": {term: [0.0 for _ in config.labels] for term in terms},
    }


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _report(weights: dict[str, Any], config: TrainingConfig, data_id: str) -> TrainingReport:
    code = hashlib.sha256(inspect.getsource(train_sparse_model).encode()).hexdigest()
    environment = f"python:{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro};{platform.python_implementation()}"
    optimizer = f"sparse-softmax-sgd-v1;config:{config.digest}"
    return build_training_report(
        code_digest=code,
        data_digest=data_id,
        environment_id=environment,
        seed=str(config.seed),
        optimizer=optimizer,
        checkpoint_digest=_digest(weights),
    )


def train_sparse_model(records: Sequence[Record], config: TrainingConfig | None = None) -> TrainingRun:
    """Fit a sparse softmax head using train rows and select by validation loss."""
    config = config or TrainingConfig()
    _validate_records(records, config)
    train, validation, excluded = _partition(records)
    terms = vocabulary(train, config)
    term_set = set(terms)
    train_examples = _labeled_examples(train, config, term_set)
    validation_examples = _labeled_examples(validation, config, term_set)
    baseline = fit_majority(train, validation, config)
    weights = _weights(config, terms)
    best_weights: dict[str, Any] | None = None
    best_loss = float("inf")
    best_epoch = 0
    history: list[EpochMetrics] = []
    for epoch in range(1, config.epochs + 1):
        update(weights, train_examples, config)
        train_loss = loss(weights, train_examples)
        validation_loss = loss(weights, validation_examples)
        checkpoint = _digest(weights)
        history.append(EpochMetrics(epoch, train_loss, validation_loss, checkpoint))
        if validation_loss < best_loss:
            best_loss, best_epoch = validation_loss, epoch
            best_weights = copy.deepcopy(weights)
    assert best_weights is not None
    data_id = data_digest((*train, *validation), config)
    checkpoint_id = _digest(best_weights)
    return TrainingRun(
        weights=best_weights,
        config_digest=config.digest,
        data_digest=data_id,
        checkpoint_digest=checkpoint_id,
        selected_epoch=best_epoch,
        history=tuple(history),
        train_count=len(train),
        validation_count=len(validation),
        excluded_counts=excluded,
        baseline=baseline,
        report=_report(best_weights, config, data_id),
    )
