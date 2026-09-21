"""Bounded JSON request admission and the first registered task."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

MAX_BYTES = 256 * 1024
ID = re.compile(r"[a-zA-Z0-9_.:-]{1,128}\Z")
SUPPORT = (
    ("bug", "Restore broken behavior"),
    ("feature", "Add behavior"),
    ("documentation", "Change explanatory material"),
    ("refactor", "Restructure without intended behavior change"),
)


def ensure(valid: bool) -> None:
    if not valid:
        raise ValueError("invalid_request")


def object_fields(value: Any, fields: set[str]) -> dict[str, Any]:
    ensure(isinstance(value, dict) and set(value) == fields)
    return dict(value)


def text(value: Any, maximum: int = 4096) -> None:
    ensure(isinstance(value, str) and 0 < len(value) <= maximum)


def identifier(value: Any) -> None:
    ensure(isinstance(value, str) and ID.fullmatch(value) is not None)


def integer(value: Any, minimum: int, maximum: int) -> None:
    ensure(type(value) is int and minimum <= value <= maximum)


def task_definition() -> dict[str, Any]:
    return {
        "task_id": "sdlc.change_type",
        "task_version": 1,
        "kind": "choice",
        "instructions": "Classify the primary intended change.",
        "support": [{"id": key, "description": description} for key, description in SUPPORT],
        "state_schema": {
            "title": "string",
            "body": "string",
            "declared_change_type": "optional string",
        },
        "languages": ["en"],
    }


def definition_hash() -> str:
    encoded = json.dumps(
        task_definition(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def example_request() -> dict[str, Any]:
    definition = task_definition()
    question = {
        key: value for key, value in definition.items() if key not in {"state_schema", "languages"}
    }
    question.update(id="change_type", definition_hash=definition_hash())
    return {
        "schema_version": "1.0",
        "request_id": "demo-001",
        "state": {"title": "Fix crash on empty config", "body": "Command exits unexpectedly."},
        "language": "en",
        "data_class": "public",
        "questions": [question],
        "constraints": {"deadline_ms": 5000, "allow_remote": False, "max_cost_usd": "0.000000"},
    }


def _depth_guard(raw: bytes) -> None:
    depth, quoted, escaped = 0, False, False
    for value in raw:
        if quoted:
            if escaped:
                escaped = False
            elif value == 92:
                escaped = True
            elif value == 34:
                quoted = False
        elif value == 34:
            quoted = True
        elif value in (91, 123):
            depth += 1
            ensure(depth <= 16)
        elif value in (93, 125):
            depth -= 1


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        ensure(key not in result)
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("invalid_request")


def _finite(value: Any) -> None:
    if isinstance(value, float):
        ensure(math.isfinite(value))
    elif isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, child in value.items():
            _finite(key)
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)


def _question(question: Any) -> None:
    q = object_fields(
        question,
        {"id", "task_id", "task_version", "definition_hash", "kind", "instructions", "support"},
    )
    identifier(q["id"])
    identifier(q["task_id"])
    integer(q["task_version"], 1, 2**31 - 1)
    ensure(
        isinstance(q["definition_hash"], str)
        and re.fullmatch(r"[a-f0-9]{64}", q["definition_hash"]) is not None
    )
    text(q["instructions"])
    ensure(q["kind"] in ("choice", "bool", "score"))
    support = q["support"]
    maximum = 21 if q["kind"] == "score" else 64
    ensure(isinstance(support, list) and 2 <= len(support) <= maximum)
    ids: set[str] = set()
    previous = -1001
    for item in support:
        fields = {"id", "value", "rubric"} if q["kind"] == "score" else {"id", "description"}
        entry = object_fields(item, fields)
        identifier(entry["id"])
        ensure(entry["id"] not in ids)
        ids.add(entry["id"])
        if q["kind"] == "score":
            integer(entry["value"], -1000, 1000)
            ensure(entry["value"] > previous)
            previous = entry["value"]
            text(entry["rubric"], 1024)
        else:
            text(entry["description"], 1024)
    if q["kind"] == "bool":
        ensure(
            support
            == [{"id": "false", "description": "False"}, {"id": "true", "description": "True"}]
        )


def parse_request(raw: bytes) -> dict[str, Any]:
    """Validate before routing/I/O; errors never carry input text."""
    try:
        ensure(len(raw) <= MAX_BYTES)
        _depth_guard(raw)
        decoded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        _finite(decoded)
        request = object_fields(
            decoded,
            {
                "schema_version",
                "request_id",
                "state",
                "language",
                "data_class",
                "questions",
                "constraints",
            },
        )
        ensure(request["schema_version"] == "1.0")
        identifier(request["request_id"])
        ensure(isinstance(request["state"], dict))
        ensure(
            isinstance(request["language"], str)
            and re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", request["language"])
            is not None
        )
        ensure(request["data_class"] in ("public", "internal", "restricted"))
        questions = request["questions"]
        ensure(isinstance(questions, list) and 1 <= len(questions) <= 32)
        ids: set[str] = set()
        for question in questions:
            _question(question)
            ensure(question["id"] not in ids)
            ids.add(question["id"])
        constraints = object_fields(
            request["constraints"], {"deadline_ms", "allow_remote", "max_cost_usd"}
        )
        integer(constraints["deadline_ms"], 1, 60_000)
        ensure(type(constraints["allow_remote"]) is bool)
        ensure(
            isinstance(constraints["max_cost_usd"], str)
            and re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?", constraints["max_cost_usd"])
            is not None
        )
        return request
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid_request") from exc
