"""Snapshot, rule conflict and capability admission behavior."""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from s1_contracts.request import definition_hash, example_request, task_definition

pytestmark = [pytest.mark.behavioral, pytest.mark.contract]


def api(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        pytest.fail(f"Missing routing behavior: {name}")


@pytest.mark.requirement("R-002")
@pytest.mark.requirement("R-012")
def test_policy_snapshot_and_conflicting_rules() -> None:
    module = api("s1router.domain.policy")
    config = module.default_policy()
    config["rules"] = [
        dict(
            id="a",
            version=1,
            priority=10,
            definition_hash=definition_hash(),
            field="declared_change_type",
            equals="bug",
            selected_id="bug",
        ),
        dict(
            id="b",
            version=1,
            priority=10,
            definition_hash=definition_hash(),
            field="declared_change_type",
            equals="bug",
            selected_id="feature",
        ),
    ]
    policy = module.PolicySnapshot.from_dict(config)
    before = policy.reference
    config["rules"][1]["priority"] = 9
    question = example_request()["questions"][0]
    assert policy.rule(question, {"declared_change_type": "bug"}) == (None, "rule_conflict", None)
    assert policy.reference == before
    resolved = module.PolicySnapshot.from_dict(config)
    assert resolved.rule(question, {"declared_change_type": "bug", "allow_remote": True}) == (
        "bug",
        None,
        "a@1",
    )
    assert policy.allow_remote is False
    assert resolved.reference != before
    assert resolved.rule(question, {}) == (None, None, None)
    config["mandatory_review_tasks"] = [question["task_id"]]
    mandatory = module.PolicySnapshot.from_dict(config)
    assert mandatory.rule(question, {"declared_change_type": "bug"}) == (
        None,
        "mandatory_review",
        None,
    )


@pytest.mark.requirement("R-002")
@pytest.mark.requirement("R-006")
@pytest.mark.parametrize(
    "field,value",
    [
        ("unknown", 1),
        ("deadline_ms", True),
        ("deadline_ms", 0),
        ("max_cost_usd", "-1"),
        ("providers", ["local", "local"]),
        ("providers", []),
        ("allow_remote", 1),
        ("allowed_endpoints", ["http://example.com"]),
        ("allowed_data_classes", ["secret"]),
        ("audit_required", False),
    ],
)
def test_invalid_policy_is_rejected(field: str, value: Any) -> None:
    module = api("s1router.domain.policy")
    config = module.default_policy()
    config[field] = value
    with pytest.raises(ValueError, match="invalid_configuration"):
        module.PolicySnapshot.from_dict(config)


@pytest.mark.requirement("R-003")
def test_full_definition_and_rendered_token_limits_before_inference() -> None:
    module = api("s1router.domain.capabilities")
    definition = task_definition()
    task = module.RegisteredTask.create(definition)
    definition["instructions"] = "caller mutation"
    request = example_request()
    question = request["questions"][0]
    caps = module.Capabilities(
        tasks=(task,),
        languages=("en",),
        max_state_tokens=10,
        max_head_tokens=10,
        max_questions=2,
        max_choices=4,
    )
    counts = {"state": 10, "head": 10}
    rendered: list[str] = []

    def count(text: str) -> int:
        rendered.append(text)
        return counts["head"] if question["instructions"] in text else counts["state"]

    assert caps.check(request, question, count) is None
    assert request["state"]["title"] in rendered[0]
    assert question["support"][3]["description"] in rendered[1]
    counts["head"] = 11
    assert caps.check(request, question, count) == "input_too_long"
    counts["head"] = 10
    counts["state"] = 11
    assert caps.check(request, question, count) == "input_too_long"
    request["language"] = "de"
    assert caps.check(request, question, count) == "unsupported_language"
    request["language"] = "en"
    question["instructions"] = "modified same hash"
    assert caps.check(request, question, count) == "unsupported_task"


@pytest.mark.requirement("R-003")
def test_capability_count_limits_and_schema() -> None:
    module = api("s1router.domain.capabilities")
    task = module.RegisteredTask.create(task_definition())
    request = example_request()
    question = request["questions"][0]
    caps = module.Capabilities(
        tasks=(task,),
        languages=("en",),
        max_state_tokens=10,
        max_head_tokens=10,
        max_questions=1,
        max_choices=3,
    )
    assert caps.check(request, question, lambda _: 1) == "too_many_choices"
    request["questions"].append(dict(question, id="another"))
    assert caps.check(request, question, lambda _: 1) == "too_many_choices"
    caps = module.Capabilities(
        tasks=(task,),
        languages=("en",),
        max_state_tokens=10,
        max_head_tokens=10,
        max_questions=2,
        max_choices=4,
    )
    request["state"]["title"] = 42
    assert caps.check(request, question, lambda _: 1) == "unsupported_task"
    with pytest.raises(ValueError):
        module.Capabilities(
            tasks=(task,),
            languages=("en",),
            max_state_tokens=0,
            max_head_tokens=10,
            max_questions=2,
            max_choices=4,
        )


@pytest.mark.requirement("R-002")
def test_policy_endpoints_lists_rules_and_noncanonical_input() -> None:
    module = api("s1router.domain.policy")
    good = module.default_policy()
    good["allowed_endpoints"] = ["https://gateway.example:8443/v1/decision"]
    assert module.PolicySnapshot.from_dict(good).config == good
    bad_changes: list[dict[str, Any]] = [
        {"allowed_endpoints": ["https://gateway.example:99999"]},
        {"allowed_endpoints": [1]},
        {"providers": "local"},
        {"providers": [""]},
        {"rules": {}},
        {"rules": [{}]},
        {"rules": [good["rules"][0], good["rules"][0]]},
        {"rules": [good["rules"][0] | {"equals": []}]},
        {"rules": [good["rules"][0] | {"definition_hash": "bad"}]},
    ]
    for changes in bad_changes:
        with pytest.raises(ValueError, match="invalid_configuration"):
            module.PolicySnapshot.from_dict(good | changes)
    for encoded in ["not json", "{}", ' {"version":1} ']:
        with pytest.raises(ValueError, match="invalid_configuration"):
            module.PolicySnapshot(encoded)
    question = example_request()["questions"][0]
    good["rules"] = [good["rules"][0] | {"selected_id": "nonexistent"}]
    assert module.PolicySnapshot.from_dict(good).rule(
        question, {"declared_change_type": "bug"}
    ) == (None, "invalid_configuration", None)


@pytest.mark.requirement("R-003")
def test_capability_bad_definitions_and_token_counts() -> None:
    module = api("s1router.domain.capabilities")
    definition_changes: list[dict[str, Any]] = [
        {"state_schema": {}},
        {"state_schema": {"title": "object"}},
        {"languages": []},
        {"languages": [42]},
        {"unknown": True},
    ]
    for changes in definition_changes:
        with pytest.raises(ValueError):
            module.RegisteredTask.create(task_definition() | changes)
    with pytest.raises(ValueError):
        module.RegisteredTask(" {} ")
    task = module.RegisteredTask.create(task_definition())
    request = example_request()
    caps = module.Capabilities(
        tasks=(task,),
        languages=("en",),
        max_state_tokens=10,
        max_head_tokens=10,
        max_questions=1,
        max_choices=4,
    )
    assert caps.check(request, request["questions"][0], lambda _: -1) == "invalid_provider_output"
    capability_changes: list[dict[str, Any]] = [
        {"tasks": []},
        {"tasks": (None,)},
        {"languages": ()},
        {"languages": (42,)},
        {"max_choices": True},
    ]
    for changes in capability_changes:
        defaults: dict[str, Any] = dict(
            tasks=(task,),
            languages=("en",),
            max_state_tokens=10,
            max_head_tokens=10,
            max_questions=1,
            max_choices=4,
        )
        with pytest.raises(ValueError):
            module.Capabilities(**(defaults | changes))
