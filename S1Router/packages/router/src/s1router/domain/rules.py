"""Immutable registered rule semantics with explicit abstention."""

from __future__ import annotations

from typing import Any

from s1_contracts.request import SUPPORT, definition_hash, task_definition


def decide(request: dict[str, Any]) -> dict[str, Any]:
    """Route an already validated request; perform no external I/O."""
    definition = task_definition()
    outcomes = []
    for question in request["questions"]:
        supported = question["definition_hash"] == definition_hash() and all(
            question[key] == definition[key]
            for key in ("task_id", "task_version", "kind", "instructions", "support")
        )
        reason: str | None = "remote_disabled"
        selected: str | None = None
        if not supported:
            reason = "unsupported_task"
        elif request["language"] != "en":
            reason = "unsupported_language"
        elif not all(isinstance(request["state"].get(key), str) for key in ("title", "body")):
            reason = "invalid_request"
        else:
            declared = request["state"].get("declared_change_type")
            if isinstance(declared, str) and declared in dict(SUPPORT):
                selected, reason = declared, None
        status = "answered_rule" if selected is not None else "review_required"
        outcomes.append(
            {
                "question_id": question["id"],
                "status": status,
                "selected_id": selected,
                "prediction": None,
                "reason": reason,
                "attempts": [
                    {
                        "rule_ref": "declared-change-type@1",
                        "status": status,
                        "reason": reason,
                        "elapsed_ms": 0.0,
                        "cost_usd": "0.000000",
                    }
                ],
            }
        )
    return {
        "schema_version": "1.0",
        "request_id": request["request_id"],
        "policy_ref": "local-rules@1",
        "task_registry_ref": definition_hash(),
        "outcomes": outcomes,
        "timings_ms": {"processing": 0.0},
        "cost_usd": "0.000000",
        "audit_ref": None,
    }
