"""Canonical immutable policy snapshots and declarative rule precedence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from s1_contracts.request import SUPPORT, definition_hash, identifier, integer, object_fields

FIELDS = set(
    (
        "version providers allow_remote allowed_endpoints allowed_data_classes deadline_ms "
        "max_cost_usd audit_required mandatory_review_tasks rules remote_auto_accept"
    ).split()
)
RULE_FIELDS = set("id version priority definition_hash field equals selected_id".split())


def default_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "providers": ["local"],
        "allow_remote": False,
        "allowed_endpoints": [],
        "allowed_data_classes": ["public"],
        "deadline_ms": 5000,
        "max_cost_usd": "0.000000",
        "audit_required": True,
        "mandatory_review_tasks": [],
        "remote_auto_accept": False,
        "rules": [
            dict(
                id=f"declared-{label}",
                version=1,
                priority=0,
                definition_hash=definition_hash(),
                field="declared_change_type",
                equals=label,
                selected_id=label,
            )
            for label, _ in SUPPORT
        ],
    }


def validate(config: Any) -> dict[str, Any]:
    try:
        value = object_fields(config, FIELDS)
        integer(value["version"], 1, 2**31 - 1)
        integer(value["deadline_ms"], 1, 60_000)
        for flag in ("allow_remote", "remote_auto_accept"):
            if type(value[flag]) is not bool:
                raise ValueError("invalid flag")
        if value["audit_required"] is not True:
            raise ValueError("this product profile requires audit")
        if not isinstance(value["max_cost_usd"], str) or not re.fullmatch(
            r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", value["max_cost_usd"]
        ):
            raise ValueError("invalid money")
        for field in (
            "providers",
            "allowed_endpoints",
            "allowed_data_classes",
            "mandatory_review_tasks",
        ):
            values = value[field]
            if (
                not isinstance(values, list)
                or len(values) > 64
                or not all(isinstance(v, str) for v in values)
                or len(values) != len(set(values))
            ):
                raise ValueError("invalid list")
        if not 1 <= len(value["providers"]) <= 8:
            raise ValueError("invalid provider count")
        for name in value["providers"] + value["mandatory_review_tasks"]:
            identifier(name)
        if any(
            item not in ("public", "internal", "restricted")
            for item in value["allowed_data_classes"]
        ):
            raise ValueError("invalid data class")
        for endpoint in value["allowed_endpoints"]:
            match = re.fullmatch(
                r"https://[A-Za-z0-9.-]+(?::([0-9]{1,5}))?(?:/[A-Za-z0-9_./%-]*)?", endpoint
            )
            if not match or (match.group(1) is not None and not 1 <= int(match.group(1)) <= 65535):
                raise ValueError("invalid endpoint")
        if not isinstance(value["rules"], list) or len(value["rules"]) > 128:
            raise ValueError("invalid rules")
        seen: set[str] = set()
        for item in value["rules"]:
            rule = object_fields(item, RULE_FIELDS)
            for field in ("id", "field", "selected_id"):
                identifier(rule[field])
            integer(rule["version"], 1, 2**31 - 1)
            integer(rule["priority"], 0, 2**31 - 1)
            if (
                rule["id"] in seen
                or not isinstance(rule["definition_hash"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", rule["definition_hash"])
            ):
                raise ValueError("invalid rule identity")
            seen.add(rule["id"])
            if rule["equals"] is not None and type(rule["equals"]) not in (str, int, bool):
                raise ValueError("rule predicates must be finite scalars")
        return value
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid_configuration") from exc


@dataclass(frozen=True)
class PolicySnapshot:
    encoded: str

    def __post_init__(self) -> None:
        try:
            value = validate(json.loads(self.encoded))
            if self.encoded != json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ):
                raise ValueError("noncanonical policy")
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid_configuration") from exc

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> PolicySnapshot:
        value = validate(config)
        return cls(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

    @property
    def config(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.encoded)
        return value

    @property
    def reference(self) -> str:
        return hashlib.sha256(self.encoded.encode()).hexdigest()

    @property
    def allow_remote(self) -> bool:
        return self.config["allow_remote"] is True

    def rule(
        self, question: dict[str, Any], state: dict[str, Any]
    ) -> tuple[str | None, str | None, str | None]:
        config = self.config
        if question["task_id"] in config["mandatory_review_tasks"]:
            return None, "mandatory_review", None
        matches = [
            r
            for r in config["rules"]
            if r["definition_hash"] == question["definition_hash"]
            and r["field"] in state
            and type(state[r["field"]]) is type(r["equals"])
            and state[r["field"]] == r["equals"]
        ]
        if not matches:
            return None, None, None
        priority = max(r["priority"] for r in matches)
        winners = sorted((r for r in matches if r["priority"] == priority), key=lambda r: r["id"])
        if len({r["selected_id"] for r in winners}) > 1:
            return None, "rule_conflict", None
        winner = winners[0]
        if winner["selected_id"] not in {item["id"] for item in question["support"]}:
            return None, "invalid_configuration", None
        return winner["selected_id"], None, f"{winner['id']}@{winner['version']}"
