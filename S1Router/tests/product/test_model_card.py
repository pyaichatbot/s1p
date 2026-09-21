"""M-012: model cards describe envelope, lineage, limitations, data, hardware, evidence."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from s1_contracts.capabilities import RegisteredTask
from s1_contracts.request import task_definition
from s1m.data.split import SplitRole
from s1m.data.validation import Record
from s1m.reporting.model_card import (
    ModelCardError,
    build_model_card,
    data_summary_from,
    lineage_from,
    task_envelope_from,
)

pytestmark = [pytest.mark.behavioral]

LIMITATIONS = (
    "Trained against experimental_fixture synthetic data only; not release-eligible "
    "for production traffic and not validated against real-world SDLC issue text."
)
HARDWARE_NOT_MEASURED = "not yet measured; no hardware benchmark has been performed (see M-013)"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def record(number: int, split: SplitRole, license_: str = "CC-BY-4.0") -> Record:
    body = f"Body for issue {number}."
    return Record(
        example_id=f"ghpr:{number}",
        group_id=f"repo:{number}",
        source_uri=f"https://example.invalid/issues/{number}",
        source_revision="2026-09-21T00:00:00Z",
        source_license=license_,
        source_license_uri="https://creativecommons.org/licenses/by/4.0/",
        source_license_digest=digest(license_),
        source_digest=digest("fixture-export"),
        collected_at="2026-09-21T00:00:00Z",
        task_id="sdlc.change_type",
        task_version="1",
        language="en",
        title=f"Issue {number}",
        body=body,
        label="bug",
        label_origin="human_adjudicated",
        reviewer_ids=("r1",),
        adjudication_status="adjudicated",
        content_hash=digest(f"Issue {number}\n{body}"),
        repository="example/repo",
        issue_number=str(number),
        source_label="bug",
        duplicate_cluster=None,
        near_duplicate_cluster=None,
        template_cluster=None,
        split=split,
    )


def sample_records() -> list[Record]:
    return [
        record(1, SplitRole.TRAIN),
        record(2, SplitRole.TRAIN),
        record(3, SplitRole.VALIDATION),
        record(4, SplitRole.CALIBRATION),
        record(5, SplitRole.FINAL_TEST, license_="MIT"),
    ]


def sample_manifest() -> dict[str, Any]:
    return {
        "files": {
            "weights.json": {"sha256": digest("weights"), "size_bytes": 7},
            "tokenizer.json": {"sha256": digest("tokenizer"), "size_bytes": 7},
        },
        "precision": "fp64",
        "runtime": "python-stdlib-v1",
        "status": "experimental_fixture",
    }


def sample_evidence() -> dict[str, Any]:
    return {"total": 40, "correct": 33, "error_rate": 0.175}


def build_valid_card() -> Any:
    task = RegisteredTask.create(task_definition())
    return build_model_card(
        task_envelope=task_envelope_from(task),
        lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
        limitations=LIMITATIONS,
        data=data_summary_from(sample_records()),
        hardware=HARDWARE_NOT_MEASURED,
        measured_evidence=sample_evidence(),
    )


@pytest.mark.requirement("M-012")
def test_fully_valid_card_builds_and_serializes_deterministically() -> None:
    card = build_valid_card()

    assert card.task_envelope["task_id"] == "sdlc.change_type"
    assert card.lineage["precision"] == "fp64"
    assert card.data["split_counts"]["train"] == 2
    assert set(card.data["licenses"]) == {"CC-BY-4.0", "MIT"}
    assert card.measured_evidence["total"] == 40

    first = build_valid_card().to_json()
    second = build_valid_card().to_json()
    assert first == second
    assert first == build_valid_card().to_json()


@pytest.mark.requirement("M-012")
def test_missing_limitations_is_rejected() -> None:
    task = RegisteredTask.create(task_definition())
    with pytest.raises(ModelCardError, match="limitations"):
        build_model_card(
            task_envelope=task_envelope_from(task),
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations="   ",
            data=data_summary_from(sample_records()),
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence=sample_evidence(),
        )


@pytest.mark.requirement("M-012")
def test_empty_measured_evidence_is_rejected() -> None:
    task = RegisteredTask.create(task_definition())
    with pytest.raises(ModelCardError, match="measured_evidence"):
        build_model_card(
            task_envelope=task_envelope_from(task),
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations=LIMITATIONS,
            data=data_summary_from(sample_records()),
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence={"total": 0, "correct": 0, "error_rate": 0.0},
        )


@pytest.mark.requirement("M-012")
def test_missing_hardware_field_is_rejected() -> None:
    task = RegisteredTask.create(task_definition())
    with pytest.raises(ModelCardError, match="hardware"):
        build_model_card(
            task_envelope=task_envelope_from(task),
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations=LIMITATIONS,
            data=data_summary_from(sample_records()),
            hardware="",
            measured_evidence=sample_evidence(),
        )


@pytest.mark.requirement("M-012")
def test_data_section_with_zero_records_is_rejected() -> None:
    task = RegisteredTask.create(task_definition())
    with pytest.raises(ModelCardError, match="data"):
        build_model_card(
            task_envelope=task_envelope_from(task),
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations=LIMITATIONS,
            data=data_summary_from([]),
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence=sample_evidence(),
        )


@pytest.mark.requirement("M-012")
def test_data_section_without_license_information_is_rejected() -> None:
    with pytest.raises(ModelCardError, match="data"):
        build_model_card(
            task_envelope=task_envelope_from(RegisteredTask.create(task_definition())),
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations=LIMITATIONS,
            data={"split_counts": {"train": 1}, "licenses": []},
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence=sample_evidence(),
        )


@pytest.mark.requirement("M-012")
def test_task_envelope_missing_required_fields_is_rejected() -> None:
    task = RegisteredTask.create(task_definition())
    envelope = task_envelope_from(task)
    del envelope["kind"]

    with pytest.raises(ModelCardError, match="task_envelope"):
        build_model_card(
            task_envelope=envelope,
            lineage=lineage_from(digest("manifest-bytes"), sample_manifest()),
            limitations=LIMITATIONS,
            data=data_summary_from(sample_records()),
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence=sample_evidence(),
        )


@pytest.mark.requirement("M-012")
def test_lineage_missing_required_fields_is_rejected() -> None:
    with pytest.raises(ModelCardError, match="lineage"):
        build_model_card(
            task_envelope=task_envelope_from(RegisteredTask.create(task_definition())),
            lineage={"manifest_hash": digest("x")},
            limitations=LIMITATIONS,
            data=data_summary_from(sample_records()),
            hardware=HARDWARE_NOT_MEASURED,
            measured_evidence=sample_evidence(),
        )
