"""Train-only deterministic word-count features for sparse model fitting."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Sequence

from s1m.data.validation import Record

from .config import TrainingConfig, TrainingError

_WORD = re.compile(r"\w+")


def _text(record: Record, config: TrainingConfig) -> str:
    text = f"{record.title}\n{record.body}"
    if len(text) > config.max_text_chars:
        raise TrainingError(f"{record.example_id}: text exceeds bound")
    return text


def tokens(record: Record, config: TrainingConfig) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in _WORD.finditer(_text(record, config)))


def vocabulary(records: Sequence[Record], config: TrainingConfig) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(tokens(record, config))
    ordered = sorted(counts, key=lambda term: (-counts[term], term))
    return tuple(ordered[: config.vocabulary_size])


def vector(record: Record, config: TrainingConfig, terms: set[str]) -> dict[str, float]:
    counts = Counter(tokens(record, config))
    return {term: float(count) for term, count in counts.items() if term in terms}


def data_digest(records: Sequence[Record], config: TrainingConfig) -> str:
    payload = [
        {
            "example_id": record.example_id,
            "group_id": record.group_id,
            "split": str(record.split),
            "label": record.label,
            "title": record.title,
            "body": record.body,
            "content_hash": record.content_hash,
        }
        for record in sorted(records, key=lambda item: item.example_id)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((config.digest + ":" + encoded).encode()).hexdigest()
