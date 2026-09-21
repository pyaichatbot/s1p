"""Application routing across finite providers without policy leakage."""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from s1_contracts.request import example_request, task_definition
from s1router.domain.capabilities import Capabilities, RegisteredTask
from s1router.domain.policy import PolicySnapshot, default_policy
from s1router.ports.providers import ProviderReply

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


class Provider:
    capabilities: Capabilities | None = None
    calibration = None
    max_cost_usd = "0.010000"

    def __init__(self, name: str, *, remote: bool = False, fail: bool = False) -> None:
        self.provider_id, self.remote, self.fail = name, remote, fail
        self.endpoint = "https://gateway.example/decision" if remote else None
        self.calls = 0
        self.capabilities = Capabilities(
            tasks=(RegisteredTask.create(task_definition()),),
            languages=("en",),
            max_state_tokens=10000,
            max_head_tokens=10000,
            max_questions=32,
            max_choices=64,
        )

    def count_tokens(self, text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        self.calls += 1
        if self.fail:
            raise TimeoutError("secret provider diagnostics")
        return ProviderReply(selected_id="bug", actual_cost_usd="0.004000")


class Audit:
    def __init__(self, fail: bool = False) -> None:
        self.records: list[dict[str, Any]] = []
        self.fail = fail

    def append(self, record: dict[str, Any]) -> str:
        if self.fail:
            raise OSError("disk full")
        self.records.append(record)
        return "record-1"


def engine(providers: list[Provider], audit: Audit, **changes: Any) -> Any:
    try:
        module = importlib.import_module("s1router.application.engine")
    except ModuleNotFoundError:
        pytest.fail("Missing full router application")
    config = default_policy() | changes
    config["providers"] = [p.provider_id for p in providers]
    return module.Router(
        PolicySnapshot.from_dict(config),
        tuple(providers),
        (RegisteredTask.create(task_definition()),),
        audit,
    )


@pytest.mark.requirement("R-001")
@pytest.mark.requirement("R-002")
@pytest.mark.requirement("R-008")
@pytest.mark.requirement("R-012")
def test_bad_request_no_io_and_rule_audit_redaction() -> None:
    provider, audit = Provider("local"), Audit()
    router = engine([provider], audit)
    with pytest.raises(ValueError, match="invalid_request"):
        router.decide(b"{}")
    assert provider.calls == 0 and not audit.records
    request = example_request()
    request["state"].update(
        declared_change_type="bug", body="unique private content", allow_remote=True
    )
    result = router.decide(json.dumps(request).encode())
    assert result["outcomes"][0]["status"] == "answered_rule"
    assert provider.calls == 0
    assert "unique private content" not in json.dumps(audit.records)
    assert request["request_id"] not in json.dumps(audit.records)
    assert result["audit_ref"] == "record-1"


@pytest.mark.requirement("R-005")
@pytest.mark.requirement("R-006")
@pytest.mark.requirement("R-007")
def test_remote_permissions_budget_and_finite_fallback() -> None:
    first, second = Provider("first", remote=True, fail=True), Provider("second", remote=True)
    audit = Audit()
    router = engine(
        [first, second],
        audit,
        allow_remote=True,
        allowed_endpoints=["https://gateway.example/decision"],
        max_cost_usd="0.020000",
        remote_auto_accept=True,
    )
    request = example_request()
    assert router.decide(json.dumps(request).encode())["outcomes"][0]["reason"] == "remote_disabled"
    assert first.calls == second.calls == 0
    request["constraints"].update(allow_remote=True, max_cost_usd="0.020000")
    result = router.decide(json.dumps(request).encode())
    assert first.calls == second.calls == 1
    assert result["outcomes"][0]["status"] == "answered_remote"
    assert result["outcomes"][0]["prediction"] is None
    assert result["cost_usd"] == "0.014000"
    request["constraints"]["max_cost_usd"] = "0.009999"
    assert (
        router.decide(json.dumps(request).encode())["outcomes"][0]["reason"] == "budget_exhausted"
    )
    assert first.calls == second.calls == 1


@pytest.mark.requirement("R-007")
@pytest.mark.requirement("R-008")
def test_audit_failure_blocks_automatic_answers_and_question_order() -> None:
    provider = Provider("remote", remote=True)
    router = engine([provider], Audit(fail=True))
    request = example_request()
    request["state"]["declared_change_type"] = "bug"
    request["questions"].append(dict(request["questions"][0], id="second"))
    result = router.decide(json.dumps(request).encode())
    assert [o["question_id"] for o in result["outcomes"]] == ["change_type", "second"]
    assert all(
        o["reason"] == "audit_unavailable" and o["selected_id"] is None for o in result["outcomes"]
    )
    assert provider.calls == 0
