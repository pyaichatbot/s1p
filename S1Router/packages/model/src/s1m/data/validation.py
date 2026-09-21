"""Provenance and schema validation for dataset ingestion (M-002)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LABELS = frozenset({"bug", "feature", "documentation", "refactor"})
LABEL_ORIGINS = frozenset({"source_weak", "human_independent", "human_adjudicated"})
ADJUDICATION_STATUSES = frozenset({"pending", "agreed", "adjudicated"})

REQUIRED_TEXT_FIELDS = (
    "example_id",
    "group_id",
    "source_uri",
    "source_revision",
    "source_license",
    "source_license_uri",
    "source_license_digest",
    "source_digest",
    "collected_at",
    "task_id",
    "task_version",
    "language",
    "title",
    "body",
    "content_hash",
    "repository",
    "issue_number",
    "source_label",
)

ALL_FIELDS = REQUIRED_TEXT_FIELDS + (
    "label",
    "label_origin",
    "reviewer_ids",
    "adjudication_status",
    "duplicate_cluster",
    "near_duplicate_cluster",
    "template_cluster",
    "split",
)


class DataValidationError(ValueError):
    """Raised when an ingested row fails provenance or schema validation."""


@dataclass(frozen=True, slots=True)
class Record:
    """A validated, typed dataset example ready for review and splitting."""

    example_id: str
    group_id: str
    source_uri: str
    source_revision: str
    source_license: str
    source_license_uri: str
    source_license_digest: str
    source_digest: str
    collected_at: str
    task_id: str
    task_version: str
    language: str
    title: str
    body: str
    label: str | None
    label_origin: str
    reviewer_ids: tuple[str, ...]
    adjudication_status: str
    content_hash: str
    repository: str
    issue_number: str
    source_label: str
    duplicate_cluster: str | None
    near_duplicate_cluster: str | None
    template_cluster: str | None
    split: str | None


def _invalid_fields(row: dict[str, object]) -> list[str]:
    invalid: list[str] = []
    for field in REQUIRED_TEXT_FIELDS:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            invalid.append(field)
    label = row.get("label")
    if label is not None and label not in LABELS:
        invalid.append("label")
    if row.get("label_origin") not in LABEL_ORIGINS:
        invalid.append("label_origin")
    if row.get("adjudication_status") not in ADJUDICATION_STATUSES:
        invalid.append("adjudication_status")
    if not isinstance(row.get("reviewer_ids"), list):
        invalid.append("reviewer_ids")
    return invalid


def _record(row: dict[str, object]) -> Record:
    reviewer_ids = row["reviewer_ids"]
    assert isinstance(reviewer_ids, list)
    return Record(
        example_id=_text(row["example_id"]),
        group_id=_text(row["group_id"]),
        source_uri=_text(row["source_uri"]),
        source_revision=_text(row["source_revision"]),
        source_license=_text(row["source_license"]),
        source_license_uri=_text(row["source_license_uri"]),
        source_license_digest=_text(row["source_license_digest"]),
        source_digest=_text(row["source_digest"]),
        collected_at=_text(row["collected_at"]),
        task_id=_text(row["task_id"]),
        task_version=_text(row["task_version"]),
        language=_text(row["language"]),
        title=_text(row["title"]),
        body=_text(row["body"]),
        label=_optional_text(row.get("label")),
        label_origin=_text(row["label_origin"]),
        reviewer_ids=tuple(str(item) for item in reviewer_ids),
        adjudication_status=_text(row["adjudication_status"]),
        content_hash=_text(row["content_hash"]),
        repository=_text(row["repository"]),
        issue_number=_text(row["issue_number"]),
        source_label=_text(row["source_label"]),
        duplicate_cluster=_optional_text(row.get("duplicate_cluster")),
        near_duplicate_cluster=_optional_text(row.get("near_duplicate_cluster")),
        template_cluster=_optional_text(row.get("template_cluster")),
        split=_optional_text(row.get("split")),
    )


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    assert isinstance(value, str)
    return value


def validate_rows(rows: list[dict[str, Any]]) -> list[Record]:
    """Validate provenance/schema for each row, returning typed records.

    Raises ``DataValidationError`` naming the offending ``example_id`` and
    the invalid field name(s) for the first row that fails validation.
    """
    records: list[Record] = []
    for row in rows:
        invalid = _invalid_fields(row)
        if invalid:
            example_id = row.get("example_id", "<unknown>")
            fields = ", ".join(invalid)
            raise DataValidationError(f"{example_id}: invalid fields: {fields}")
        records.append(_record(row))
    return records
