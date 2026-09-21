"""Immutable registered tasks and admission before provider inference."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from s1_contracts.request import _question, identifier, object_fields


@dataclass(frozen=True)
class RegisteredTask:
    encoded: str

    def __post_init__(self) -> None:
        try:
            value = object_fields(
                json.loads(self.encoded),
                {
                    "task_id",
                    "task_version",
                    "kind",
                    "instructions",
                    "support",
                    "state_schema",
                    "languages",
                },
            )
            identifier(value["task_id"])
            _question(
                {
                    key: item
                    for key, item in value.items()
                    if key not in {"state_schema", "languages"}
                }
                | {"id": "registered", "definition_hash": self.reference}
            )
            if (
                not isinstance(value["state_schema"], dict)
                or not value["state_schema"]
                or any(
                    not isinstance(key, str) or kind not in ("string", "optional string")
                    for key, kind in value["state_schema"].items()
                )
            ):
                raise ValueError("invalid state schema")
            languages = value["languages"]
            if (
                not isinstance(languages, list)
                or not languages
                or any(not isinstance(lang, str) or not lang for lang in languages)
            ):
                raise ValueError("invalid languages")
            if self.encoded != json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ):
                raise ValueError("noncanonical definition")
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_configuration") from exc

    @classmethod
    def create(cls, definition: dict[str, Any]) -> RegisteredTask:
        return cls(
            json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        )

    @property
    def reference(self) -> str:
        return hashlib.sha256(self.encoded.encode()).hexdigest()

    @property
    def definition(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.encoded)
        return value

    def matches(self, question: dict[str, Any], state: dict[str, Any]) -> bool:
        definition = self.definition
        if question["definition_hash"] != self.reference or any(
            question[key] != definition[key]
            for key in ("task_id", "task_version", "kind", "instructions", "support")
        ):
            return False
        return all(
            (kind == "optional string" and key not in state) or isinstance(state.get(key), str)
            for key, kind in definition["state_schema"].items()
        )


def render(state: dict[str, Any], question: dict[str, Any]) -> tuple[str, str]:
    return (
        json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        json.dumps(
            {
                key: question[key]
                for key in ("task_id", "task_version", "kind", "instructions", "support")
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    )


def check_task_identity(tasks: tuple[RegisteredTask, ...]) -> None:
    """Reject same task_id+task_version pairs whose content hash differs.

    A task_version is an immutable commitment to one exact definition.
    Re-registering an identical definition under the same identity is
    idempotent and allowed; registering a renamed/reordered/altered
    definition under that same identity without bumping task_version is
    an identity violation and must be rejected.
    """
    seen: dict[tuple[Any, Any], str] = {}
    for task in tasks:
        definition = task.definition
        identity = (definition["task_id"], definition["task_version"])
        reference = task.reference
        prior = seen.get(identity)
        if prior is not None and prior != reference:
            raise ValueError("invalid_configuration")
        seen[identity] = reference


@dataclass(frozen=True)
class Capabilities:
    tasks: tuple[RegisteredTask, ...]
    languages: tuple[str, ...]
    max_state_tokens: int
    max_head_tokens: int
    max_questions: int
    max_choices: int

    def __post_init__(self) -> None:
        if (
            type(self.tasks) is not tuple
            or not self.tasks
            or not all(isinstance(task, RegisteredTask) for task in self.tasks)
            or type(self.languages) is not tuple
            or not self.languages
            or not all(isinstance(lang, str) and bool(lang) for lang in self.languages)
            or any(
                type(value) is not int or value <= 0
                for value in (
                    self.max_state_tokens,
                    self.max_head_tokens,
                    self.max_questions,
                    self.max_choices,
                )
            )
        ):
            raise ValueError("invalid_configuration")
        check_task_identity(self.tasks)

    def check(
        self, request: dict[str, Any], question: dict[str, Any], count_tokens: Callable[[str], int]
    ) -> str | None:
        task = next((task for task in self.tasks if task.matches(question, request["state"])), None)
        if task is None:
            return "unsupported_task"
        if (
            request["language"] not in self.languages
            or request["language"] not in task.definition["languages"]
        ):
            return "unsupported_language"
        if (
            len(question["support"]) > self.max_choices
            or len(request["questions"]) > self.max_questions
        ):
            return "too_many_choices"
        state, head = render(request["state"], question)
        counts = (count_tokens(state), count_tokens(head))
        if any(type(count) is not int or count < 0 for count in counts):
            return "invalid_provider_output"
        if counts[0] > self.max_state_tokens or counts[1] > self.max_head_tokens:
            return "input_too_long"
        return None
