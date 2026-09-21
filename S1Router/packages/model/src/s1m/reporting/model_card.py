"""Model cards: task envelope, lineage, limitations, data, hardware, evidence (M-012).

A model card here is a pure aggregation/validation/serialization step: it
takes explicit, already-validated structured inputs -- a task envelope, a
bundle's lineage (as produced by ``s1m.artifacts.manifest.load``), a
non-empty limitations statement, dataset provenance (as
``s1m.data.validation.Record`` values), an honest hardware description and
computed measured evidence -- and either builds a well-formed ``ModelCard``
or raises ``ModelCardError`` naming every missing/invalid section. It never
measures, trains or fabricates anything; every field must trace back to a
real caller-supplied value.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from s1_contracts.capabilities import RegisteredTask

from s1m.data.validation import Record

_ENVELOPE_FIELDS = ("task_id", "task_version", "kind", "instructions", "languages")
_LINEAGE_FIELDS = ("manifest_hash", "precision", "runtime", "status", "file_digests")
_DATA_FIELDS = ("split_counts", "licenses")
_EVIDENCE_FIELDS = ("total", "correct", "error_rate")


class ModelCardError(ValueError):
    """Raised when one or more model-card sections are missing or invalid."""


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _envelope_problems(envelope: Any) -> list[str]:
    if not isinstance(envelope, dict) or set(envelope) != set(_ENVELOPE_FIELDS):
        return ["task_envelope: missing required fields"]
    problems = [
        f"task_envelope.{field}: must be a non-empty string"
        for field in ("task_id", "kind", "instructions")
        if not _nonempty_str(envelope[field])
    ]
    if envelope["task_version"] is None or envelope["task_version"] == "":
        problems.append("task_envelope.task_version: must be present")
    languages = envelope["languages"]
    if (
        not isinstance(languages, (list, tuple))
        or not languages
        or any(not _nonempty_str(lang) for lang in languages)
    ):
        problems.append("task_envelope.languages: must be a non-empty list of strings")
    return problems


def _lineage_problems(lineage: Any) -> list[str]:
    if not isinstance(lineage, dict) or set(lineage) != set(_LINEAGE_FIELDS):
        return ["lineage: missing required fields"]
    problems = [
        f"lineage.{field}: must be a non-empty string"
        for field in ("manifest_hash", "precision", "runtime", "status")
        if not _nonempty_str(lineage[field])
    ]
    digests = lineage["file_digests"]
    if (
        not isinstance(digests, dict)
        or not digests
        or any(
            not _nonempty_str(name) or not _nonempty_str(digest) for name, digest in digests.items()
        )
    ):
        problems.append("lineage.file_digests: must be a non-empty mapping of non-empty strings")
    return problems


def _data_problems(data: Any) -> list[str]:
    if not isinstance(data, dict) or set(data) != set(_DATA_FIELDS):
        return ["data: missing required fields"]
    problems: list[str] = []
    counts = data["split_counts"]
    if (
        not isinstance(counts, dict)
        or not counts
        or any(type(value) is not int or value < 0 for value in counts.values())
        or sum(counts.values()) <= 0
    ):
        problems.append("data.split_counts: must contain at least one dataset example")
    licenses = data["licenses"]
    if (
        not isinstance(licenses, (list, tuple))
        or not licenses
        or any(not _nonempty_str(item) for item in licenses)
    ):
        problems.append("data.licenses: must name at least one source license")
    return problems


def _evidence_problems(evidence: Any) -> list[str]:
    if not isinstance(evidence, dict) or set(evidence) != set(_EVIDENCE_FIELDS):
        return ["measured_evidence: missing required fields"]
    problems: list[str] = []
    total, correct, error_rate = evidence["total"], evidence["correct"], evidence["error_rate"]
    if type(total) is not int or total <= 0:
        problems.append("measured_evidence.total: must be a positive integer")
    if type(correct) is not int or not (0 <= correct <= (total if type(total) is int else 0)):
        problems.append("measured_evidence.correct: must be between 0 and total")
    if not isinstance(error_rate, (int, float)) or not (0.0 <= float(error_rate) <= 1.0):
        problems.append("measured_evidence.error_rate: must be between 0 and 1")
    return problems


def task_envelope_from(task: RegisteredTask) -> dict[str, Any]:
    """Extract the model-card task envelope subset from a ``RegisteredTask``."""
    definition = task.definition
    return {field: definition[field] for field in _ENVELOPE_FIELDS}


def lineage_from(manifest_hash: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Extract the model-card lineage subset from ``s1m.artifacts.manifest.load`` output."""
    files = manifest["files"]
    return {
        "manifest_hash": manifest_hash,
        "precision": manifest["precision"],
        "runtime": manifest["runtime"],
        "status": manifest["status"],
        "file_digests": {name: entry["sha256"] for name, entry in files.items()},
    }


def data_summary_from(records: list[Record]) -> dict[str, Any]:
    """Derive split composition and license provenance from validated records."""
    counts = Counter(str(record.split) for record in records)
    licenses = sorted({record.source_license for record in records})
    return {"split_counts": dict(counts), "licenses": licenses}


@dataclass(frozen=True)
class ModelCard:
    """A validated, deterministically serializable model card (M-012)."""

    task_envelope: dict[str, Any]
    lineage: dict[str, Any]
    limitations: str
    data: dict[str, Any]
    hardware: str
    measured_evidence: dict[str, Any]

    def __post_init__(self) -> None:
        problems = [
            *_envelope_problems(self.task_envelope),
            *_lineage_problems(self.lineage),
            *_data_problems(self.data),
            *_evidence_problems(self.measured_evidence),
        ]
        if not _nonempty_str(self.limitations):
            problems.append("limitations: must be a non-empty statement of what is not validated")
        if not _nonempty_str(self.hardware):
            problems.append("hardware: must be present, even as an explicit not-measured string")
        if problems:
            raise ModelCardError("invalid model card: " + "; ".join(problems))

    def to_json(self) -> str:
        """Canonical, deterministic serialization (sorted keys, compact separators)."""
        payload = {
            "task_envelope": self.task_envelope,
            "lineage": self.lineage,
            "limitations": self.limitations,
            "data": self.data,
            "hardware": self.hardware,
            "measured_evidence": self.measured_evidence,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_model_card(
    *,
    task_envelope: dict[str, Any],
    lineage: dict[str, Any],
    limitations: str,
    data: dict[str, Any],
    hardware: str,
    measured_evidence: dict[str, Any],
) -> ModelCard:
    """Build a fully validated ``ModelCard`` from explicit, typed section inputs."""
    return ModelCard(
        task_envelope=dict(task_envelope),
        lineage=dict(lineage),
        limitations=limitations,
        data=dict(data),
        hardware=hardware,
        measured_evidence=dict(measured_evidence),
    )
