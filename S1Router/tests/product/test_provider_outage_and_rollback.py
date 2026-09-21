"""R-013: provider outage and router-level rollback (fallback/recovery) drills.

These are end-to-end behavioral drills through the real composition
(``Router`` + ``attempt()`` + the real ``CircuitBreaker``) against a
controllable fake provider, distinct from the unit-level breaker/attempt
fault-injection tests in ``test_hardening_gaps.py`` and
``test_attempt_controls.py``: those exercise ``attempt()`` and
``CircuitBreaker`` in isolation with a single call each; these run the
breaker's *stateful* admission policy across many sequential
``Router.decide()`` calls, the way a real sustained provider outage and its
eventual recovery actually unfold.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from s1_contracts.request import example_request
from s1router.application.engine import Router
from s1router.domain.acceptance import CalibrationProfile
from s1router.domain.capabilities import Capabilities, RegisteredTask
from s1router.domain.policy import PolicySnapshot, default_policy
from s1router.ports.providers import ProviderFailure, ProviderReply

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


class FakeClock:
    """Deterministic, explicitly advanceable clock for cooldown drills."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _task() -> RegisteredTask:
    from s1_contracts.request import task_definition

    return RegisteredTask.create(task_definition())


def _prediction(question: dict[str, Any]) -> dict[str, Any]:
    provenance = {
        "provider_id": "local",
        "model_ref": "checkpoint@sha256",
        "tokenizer_hash": "a" * 64,
        "preprocessor_hash": "b" * 64,
        "definition_hash": question["definition_hash"],
        "precision": "fp32",
        "runtime_version": "cpu@1",
        "calibration_ref": "temperature@1",
    }
    return {
        "question_id": question["id"],
        "status": "predicted",
        "probabilities": [
            {"id": "bug", "probability": 0.97},
            {"id": "feature", "probability": 0.01},
            {"id": "documentation", "probability": 0.01},
            {"id": "refactor", "probability": 0.01},
        ],
        "selected_id": "bug",
        "confidence": 0.97,
        "p_true": None,
        "expected_value": None,
        "calibration_status": "calibrated",
        "provenance": provenance,
        "reason": None,
    }


class FlakyLocalProvider:
    """A local provider whose outage is toggled explicitly by the drill."""

    provider_id = "local"
    remote = False
    endpoint: str | None = None
    max_cost_usd = "0.000000"
    capabilities: Capabilities | None = None
    calibration: CalibrationProfile | None = None

    def __init__(self, question: dict[str, Any]) -> None:
        self.calls = 0
        self.fail = False
        self.capabilities = Capabilities(
            tasks=(_task(),),
            languages=("en",),
            max_state_tokens=10000,
            max_head_tokens=10000,
            max_questions=32,
            max_choices=64,
        )
        prediction = _prediction(question)
        self.calibration = CalibrationProfile.create(
            prediction["provenance"],
            dataset_hash="d" * 64,
            expires_at=1e12,
            probability=0.9,
            margin=0.1,
        )
        self._prediction = prediction

    def count_tokens(self, text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        self.calls += 1
        if self.fail:
            raise ProviderFailure("provider_unavailable")
        return ProviderReply(prediction=copy.deepcopy(self._prediction))


class Audit:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> str:
        self.records.append(record)
        return f"record-{len(self.records)}"


def _router(provider: FlakyLocalProvider, clock: FakeClock) -> Router:
    config = default_policy() | {"providers": ["local"]}
    return Router(
        PolicySnapshot.from_dict(config),
        (provider,),
        (_task(),),
        Audit(),
        clock=clock,
        wall_clock=lambda: 100.0,
    )


def _decide(router: Router) -> dict[str, Any]:
    request = example_request()
    return router.decide(json.dumps(request).encode())


@pytest.mark.requirement("R-013")
def test_sustained_provider_outage_opens_the_breaker_and_stops_dispatch() -> None:
    """A real provider outage across many requests trips the breaker cleanly.

    Every one of the first ``failure_threshold`` requests genuinely dispatches
    to the failing provider and gets a well-defined ``provider_unavailable``
    outcome (never a raw exception, never an incorrect accept). Once the
    breaker has opened, further requests during the outage window are refused
    admission before ever reaching the provider: the outage is contained, not
    just individually tolerated.
    """
    clock = FakeClock()
    provider = FlakyLocalProvider(example_request()["questions"][0])
    provider.fail = True
    router = _router(provider, clock)

    for _ in range(5):
        result = _decide(router)
        assert result["outcomes"][0]["reason"] == "provider_unavailable"
        assert result["outcomes"][0]["status"] == "review_required"
    assert provider.calls == 5

    for _ in range(3):
        result = _decide(router)
        assert result["outcomes"][0]["reason"] == "provider_unavailable"
    assert provider.calls == 5, "breaker must stop dispatching to the down provider"


@pytest.mark.requirement("R-013")
def test_router_recovers_after_provider_outage_cooldown_with_no_incorrect_accept() -> None:
    """Router-level rollback: fall back to safety during an outage, then
    resume trusting the provider once it genuinely recovers -- never the
    other way around.

    While the provider is down every outcome must be a safe
    ``review_required``/``provider_unavailable`` (no fabricated answer, no
    silent data loss). Once real time has passed the breaker's cooldown and
    the provider is healthy again, the very next request must be answered
    correctly and normally, proving the router "rolls back" onto the healthy
    path rather than staying wedged in its degraded fallback state forever.
    """
    clock = FakeClock()
    provider = FlakyLocalProvider(example_request()["questions"][0])
    provider.fail = True
    router = _router(provider, clock)

    for _ in range(5):
        outcome = _decide(router)["outcomes"][0]
        assert outcome["status"] == "review_required"
        assert outcome["selected_id"] is None

    degraded = _decide(router)["outcomes"][0]
    assert degraded["reason"] == "provider_unavailable"
    assert provider.calls == 5, "breaker open: no call while still inside the cooldown window"

    clock.advance(30.1)
    provider.fail = False

    recovered = _decide(router)["outcomes"][0]
    assert recovered["status"] == "answered_local"
    assert recovered["selected_id"] == "bug"
    assert recovered["reason"] is None
    assert provider.calls == 6

    again = _decide(router)["outcomes"][0]
    assert again["status"] == "answered_local"
    assert provider.calls == 7, "breaker closed: normal service resumed, not stuck half-open"
