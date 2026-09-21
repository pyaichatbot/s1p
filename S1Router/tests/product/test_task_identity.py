"""M-001: task identity is an immutable commitment to one exact definition."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from s1_contracts.capabilities import Capabilities, RegisteredTask, check_task_identity
from s1_contracts.request import task_definition

pytestmark = [pytest.mark.behavioral]


def build_capabilities(tasks: tuple[RegisteredTask, ...]) -> Capabilities:
    return Capabilities(
        tasks=tasks,
        languages=("en",),
        max_state_tokens=10000,
        max_head_tokens=10000,
        max_questions=32,
        max_choices=64,
    )


@pytest.mark.requirement("M-001")
def test_identical_redefinition_of_same_identity_is_idempotent() -> None:
    first = RegisteredTask.create(task_definition())
    second = RegisteredTask.create(copy.deepcopy(task_definition()))

    check_task_identity((first, second))
    build_capabilities((first, second))


@pytest.mark.requirement("M-001")
def test_reordered_support_options_under_same_identity_is_rejected() -> None:
    definition = task_definition()
    reordered = copy.deepcopy(definition)
    reordered["support"] = list(reversed(reordered["support"]))

    original = RegisteredTask.create(definition)
    changed = RegisteredTask.create(reordered)

    with pytest.raises(ValueError, match="invalid_configuration"):
        check_task_identity((original, changed))
    with pytest.raises(ValueError, match="invalid_configuration"):
        build_capabilities((original, changed))


@pytest.mark.requirement("M-001")
def test_renamed_support_option_under_same_identity_is_rejected() -> None:
    definition = task_definition()
    renamed = copy.deepcopy(definition)
    renamed["support"][0] = dict(renamed["support"][0], id="renamed_bug")

    original = RegisteredTask.create(definition)
    changed = RegisteredTask.create(renamed)

    with pytest.raises(ValueError, match="invalid_configuration"):
        check_task_identity((original, changed))


@pytest.mark.requirement("M-001")
def test_altered_instructions_under_same_identity_is_rejected() -> None:
    definition = task_definition()
    altered: dict[str, Any] = copy.deepcopy(definition)
    altered["instructions"] = "Classify the primary intended change, urgently."

    original = RegisteredTask.create(definition)
    changed = RegisteredTask.create(altered)

    with pytest.raises(ValueError, match="invalid_configuration"):
        check_task_identity((original, changed))
    with pytest.raises(ValueError, match="invalid_configuration"):
        build_capabilities((original, changed))


@pytest.mark.requirement("M-001")
def test_new_task_version_for_altered_content_is_accepted() -> None:
    definition = task_definition()
    bumped: dict[str, Any] = copy.deepcopy(definition)
    bumped["task_version"] = definition["task_version"] + 1
    bumped["instructions"] = "Classify the primary intended change, urgently."

    original = RegisteredTask.create(definition)
    next_version = RegisteredTask.create(bumped)

    check_task_identity((original, next_version))
    build_capabilities((original, next_version))
