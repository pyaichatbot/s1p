"""Strict redacted audit-record admission for verification and replay."""

from __future__ import annotations

import json
import re
from typing import Any

from s1_contracts.prediction import REASONS, finite
from s1_contracts.request import _constant, _depth_guard, _pairs, ensure, object_fields

MAX_AUDIT_BYTES = 64 * 1024
AUDIT_FIELDS = {
    "schema_version",
    "policy_ref",
    "task_registry_ref",
    "input_sha256",
    "cost_usd",
    "duration_ms",
    "outcomes",
}
STATUSES = {"answered_rule", "answered_local", "answered_remote", "review_required", "error"}


def load_record(raw: bytes) -> dict[str, Any]:
    """Reject malformed or unbounded records without echoing their contents."""
    try:
        ensure(len(raw) <= MAX_AUDIT_BYTES)
        _depth_guard(raw)
        record = object_fields(
            json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant),
            AUDIT_FIELDS,
        )
        ensure(record["schema_version"] == "1.0")
        for key in ("policy_ref", "task_registry_ref", "input_sha256"):
            ensure(
                isinstance(record[key], str)
                and re.fullmatch(r"[a-f0-9]{64}", record[key]) is not None
            )
        ensure(
            isinstance(record["cost_usd"], str)
            and re.fullmatch(r"(?:0|[1-9][0-9]{0,17})\.[0-9]{6}", record["cost_usd"]) is not None
        )
        ensure(finite(record["duration_ms"], 0, 1e15))
        outcomes = record["outcomes"]
        ensure(isinstance(outcomes, list) and len(outcomes) <= 32)
        for index, value in enumerate(outcomes):
            item = object_fields(value, {"index", "status", "reason"})
            ensure(type(item["index"]) is int and item["index"] == index)
            ensure(isinstance(item["status"], str) and item["status"] in STATUSES)
            ensure(
                item["reason"] is None
                or isinstance(item["reason"], str)
                and item["reason"] in REASONS
            )
            ensure((item["reason"] is None) == item["status"].startswith("answered_"))
        return record
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise ValueError("invalid_record") from exc
