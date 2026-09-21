"""Independent human review and adjudication merge (M-002)."""

from __future__ import annotations

import json
from dataclasses import replace

from s1m.data.validation import Record


class ReviewError(ValueError):
    """Raised when reviewer submissions cannot be merged without adjudication."""


def build_review_packet(records: list[Record], reviewer_id: str) -> str:
    """Build a deterministic JSONL review packet that hides the weak label.

    Records are sorted by ``example_id`` and rendered with sorted keys so
    that the same input always produces a byte-identical packet. The
    heuristic ``source_label`` is deliberately omitted so a reviewer cannot
    anchor on it.
    """
    lines = []
    for record in sorted(records, key=lambda item: item.example_id):
        payload = {
            "example_id": record.example_id,
            "task_id": record.task_id,
            "task_version": record.task_version,
            "language": record.language,
            "title": record.title,
            "body": record.body,
            "reviewer_id": reviewer_id,
        }
        lines.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines)


def _parse_lines(jsonl: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in jsonl.splitlines() if line.strip()]


def _entries(blobs: tuple[str, ...]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for jsonl in blobs:
        entries.extend(_parse_lines(jsonl))
    return entries


def _submissions_by_example(
    submissions: tuple[str, ...],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for entry in _entries(submissions):
        if "reviewer_id" not in entry:
            continue
        example_id = entry["example_id"]
        assert isinstance(example_id, str)
        grouped.setdefault(example_id, []).append(entry)
    return grouped


def _adjudications_by_example(
    submissions: tuple[str, ...], adjudication_jsonl: str | None
) -> dict[str, dict[str, object]]:
    blobs = submissions + ((adjudication_jsonl,) if adjudication_jsonl is not None else ())
    resolved: dict[str, dict[str, object]] = {}
    for entry in _entries(blobs):
        if "adjudicator_id" not in entry:
            continue
        example_id = entry["example_id"]
        assert isinstance(example_id, str)
        resolved[example_id] = entry
    return resolved


def _merge_one(
    record: Record,
    reviews: list[dict[str, object]],
    adjudications: dict[str, dict[str, object]],
) -> Record:
    labels = {str(entry["label"]) for entry in reviews}
    reviewer_ids = tuple(str(entry["reviewer_id"]) for entry in reviews)
    if len(labels) == 1:
        return replace(
            record,
            label=next(iter(labels)),
            label_origin="human_independent",
            adjudication_status="agreed",
            reviewer_ids=reviewer_ids,
        )
    adjudication = adjudications.get(record.example_id)
    if adjudication is None:
        raise ReviewError(
            f"{record.example_id}: reviewers disagree ({sorted(labels)}); "
            "explicit adjudication is required"
        )
    return replace(
        record,
        label=str(adjudication["label"]),
        label_origin="human_adjudicated",
        adjudication_status="adjudicated",
        reviewer_ids=reviewer_ids,
    )


def merge_review_submissions(
    records: list[Record],
    *reviewer_submission_jsonl: str,
    adjudication_jsonl: str | None = None,
) -> list[Record]:
    """Merge independent reviewer submissions (and optional adjudication).

    Two independent reviewers who agree on a label produce a
    ``human_independent`` label. Disagreement raises ``ReviewError`` unless
    an adjudicator's JSONL submission is supplied, in which case the
    adjudicator's label wins and the record becomes ``human_adjudicated``.
    Records with no matching submissions are returned unchanged.
    """
    reviews = _submissions_by_example(reviewer_submission_jsonl)
    adjudications = _adjudications_by_example(reviewer_submission_jsonl, adjudication_jsonl)
    merged: list[Record] = []
    for record in records:
        matches = reviews.get(record.example_id)
        if not matches:
            merged.append(record)
            continue
        merged.append(_merge_one(record, matches, adjudications))
    return merged
