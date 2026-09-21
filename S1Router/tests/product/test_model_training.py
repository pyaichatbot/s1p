"""Behavioral coverage for the offline sparse training slice."""

from __future__ import annotations

import hashlib

import pytest

from s1m.data.split import SplitRole
from s1m.data.validation import Record
from s1m.inference.linear import SparseLinear
from s1m.training import TrainingConfig, TrainingError, train_sparse_model

pytestmark = [pytest.mark.behavioral]


def record(number: int, split: SplitRole, label: str, **changes: object) -> Record:
    values: dict[str, object] = {
        "example_id": f"train:{number}",
        "group_id": f"group:{number}",
        "source_uri": "https://example.invalid/data",
        "source_revision": "fixture-v1",
        "source_license": "CC-BY-4.0",
        "source_license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "source_license_digest": hashlib.sha256(b"license").hexdigest(),
        "source_digest": hashlib.sha256(b"fixture").hexdigest(),
        "collected_at": "2026-09-21T00:00:00Z",
        "task_id": "sdlc.change_type",
        "task_version": "1",
        "language": "en",
        "title": f"Example {number}",
        "body": f"{label} body {number}",
        "label": label,
        "label_origin": "human_independent",
        "reviewer_ids": ("a", "b"),
        "adjudication_status": "agreed",
        "content_hash": hashlib.sha256(f"{number}".encode()).hexdigest(),
        "repository": f"example/repo-{number}",
        "issue_number": str(number),
        "source_label": label,
        "duplicate_cluster": None,
        "near_duplicate_cluster": None,
        "template_cluster": None,
        "split": split,
    }
    values.update(changes)
    return Record(**values)


def fixture_records() -> list[Record]:
    return [
        record(1, SplitRole.TRAIN, "bug", title="crash", body="crash crash"),
        record(2, SplitRole.TRAIN, "feature", title="new", body="new new"),
        record(3, SplitRole.TRAIN, "documentation", title="docs", body="docs"),
        record(4, SplitRole.VALIDATION, "bug", title="crash", body="crash"),
        record(5, SplitRole.VALIDATION, "feature", title="new", body="new"),
        record(6, SplitRole.CALIBRATION, "bug", title="calibration-only", body="secret"),
        record(7, SplitRole.FINAL_TEST, "feature", title="final-only", body="secret"),
    ]


@pytest.mark.requirement("FEAT-007")
def test_training_produces_compatible_weights_and_excludes_non_fit_roles() -> None:
    run = train_sparse_model(
        fixture_records(),
        TrainingConfig(seed=11, epochs=5, learning_rate=0.25, vocabulary_size=8),
    )

    model = SparseLinear(run.weights, list(run.weights["labels"]))
    assert set(run.weights["features"]) <= {"crash", "new", "docs", "example"}
    assert "secret" not in run.weights["features"]
    assert model.probabilities("crash")
    assert run.train_count == 3
    assert run.validation_count == 2
    assert run.excluded_counts == {"calibration": 1, "final_test": 1}


@pytest.mark.requirement("FEAT-007")
def test_checkpoint_selection_uses_validation_loss_and_records_real_history() -> None:
    run = train_sparse_model(
        fixture_records(), TrainingConfig(seed=3, epochs=6, learning_rate=0.2)
    )

    assert len(run.history) == 6
    assert run.selected_epoch == min(run.history, key=lambda item: item.validation_loss).epoch
    assert all(item.train_loss >= 0 and item.validation_loss >= 0 for item in run.history)
    assert run.checkpoint_digest != hashlib.sha256(b"placeholder").hexdigest()
    assert run.report.checkpoint_digest == run.checkpoint_digest
    assert run.report.data_digest == run.data_digest


@pytest.mark.requirement("FEAT-007")
def test_same_seed_and_config_reproduce_weights_history_and_digests() -> None:
    config = TrainingConfig(seed=19, epochs=4, learning_rate=0.15)
    first = train_sparse_model(fixture_records(), config)
    second = train_sparse_model(fixture_records(), config)

    assert first.weights == second.weights
    assert first.history == second.history
    assert first.config_digest == second.config_digest
    assert first.checkpoint_digest == second.checkpoint_digest
    assert first.report.canonical_json() == second.report.canonical_json()


@pytest.mark.requirement("FEAT-007")
def test_lineage_overlap_fails_before_any_gradient_update() -> None:
    records = fixture_records()
    records[3] = record(
        4,
        SplitRole.VALIDATION,
        "bug",
        group_id=records[0].group_id,
        repository=records[0].repository,
    )

    with pytest.raises(TrainingError, match="leakage"):
        train_sparse_model(records, TrainingConfig(epochs=2))


@pytest.mark.requirement("FEAT-008")
def test_majority_baseline_is_fitted_on_train_and_measured_on_validation() -> None:
    run = train_sparse_model(fixture_records(), TrainingConfig(seed=5, epochs=2))

    assert run.baseline.majority_label == "bug"
    assert run.baseline.train_counts == {"bug": 1, "feature": 1, "documentation": 1}
    assert run.baseline.validation_count == 2
    assert run.baseline.correct == 1
    assert run.baseline.accuracy == pytest.approx(0.5)
    assert run.baseline.fitted_split == SplitRole.TRAIN
    assert run.baseline.measured_split == SplitRole.VALIDATION


@pytest.mark.requirement("FEAT-007")
@pytest.mark.parametrize(
    "changes",
    [{"epochs": 0}, {"epochs": 1001}, {"vocabulary_size": 0}, {"vocabulary_size": 10001}],
)
def test_training_bounds_are_rejected(changes: dict[str, int]) -> None:
    with pytest.raises(TrainingError, match="bound"):
        train_sparse_model(fixture_records(), TrainingConfig(**changes))

