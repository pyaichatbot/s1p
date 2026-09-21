"""Group-aware, leakage-checked dataset splitting (M-003)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from enum import StrEnum

from s1m.data.validation import Record

REVIEWED_LABEL_ORIGINS = frozenset({"human_independent", "human_adjudicated"})

#: Fields whose values must never span more than one split. ``repository``
#: and ``content_hash`` catch repository/issue and exact-duplicate lineage
#: leakage; the remaining cluster fields catch near-duplicate and
#: template-family leakage (``None`` values are not clustered).
LEAKAGE_FIELDS = (
    "repository",
    "content_hash",
    "duplicate_cluster",
    "near_duplicate_cluster",
    "template_cluster",
)


class SplitRole(StrEnum):
    """The four disjoint roles a dataset example may be assigned."""

    TRAIN = "train"
    VALIDATION = "validation"
    CALIBRATION = "calibration"
    FINAL_TEST = "final_test"


class SplitLeakageError(ValueError):
    """Raised when a group, duplicate or template lineage spans splits."""


def validate_splits(records: list[Record]) -> None:
    """Raise ``SplitLeakageError`` if any lineage field spans multiple splits."""
    violations: list[str] = []
    for field in LEAKAGE_FIELDS:
        values: dict[str, set[str | None]] = {}
        for record in records:
            value = getattr(record, field)
            if value is None:
                continue
            values.setdefault(value, set()).add(record.split)
        if any(len(splits) > 1 for splits in values.values()):
            violations.append(field)
    if violations:
        fields = ", ".join(violations)
        raise SplitLeakageError(f"cross-split lineage leakage detected in fields: {fields}")


def _bucket(seed: str, group_id: str, modulus: int) -> int:
    digest = hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest()
    return int(digest, 16) % modulus


def _role_for(record: Record, seed: str) -> SplitRole:
    bucket = _bucket(seed, record.group_id, modulus=100)
    if record.label_origin in REVIEWED_LABEL_ORIGINS:
        if bucket < 10:
            return SplitRole.FINAL_TEST
        if bucket < 20:
            return SplitRole.CALIBRATION
        if bucket < 30:
            return SplitRole.VALIDATION
        return SplitRole.TRAIN
    if bucket < 20:
        return SplitRole.VALIDATION
    return SplitRole.TRAIN


def assign_splits(records: list[Record], seed: str) -> list[Record]:
    """Deterministically assign each record a split role.

    Assignment is keyed by ``group_id`` so identical seeds always produce
    identical results. Only reviewed records (``label_origin`` set by human
    review) are ever eligible for ``CALIBRATION`` or ``FINAL_TEST``, since
    those roles require adjudicated ground truth rather than weak labels.
    """
    return [replace(record, split=_role_for(record, seed)) for record in records]
