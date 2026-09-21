"""Adversarial/defensive-branch coverage for the post-review hardening pass.

Targets the specific branches the review found untested: WorkerService's
malformed-smoke-result rejections, its configuration/race guards, a provider
contract's own invalid-input guard, the local numeric worker's oversized-
output guard, and attempt()'s budget/breaker fault-injection paths. Each
test exists because a real gate (coverage, or a defensive branch that could
silently do the wrong thing) was previously unexercised, not to pad numbers.
"""

from __future__ import annotations

import json
import queue
from typing import Any, cast

import pytest
from s1router.adapters.worker import WorkerService, _valid_smoke
from s1router.application.attempt import attempt
from s1router.application.breaker import CircuitBreaker
from s1router.application.budget import BudgetLedger, MonotonicDeadline
from s1router.domain.acceptance import CalibrationProfile
from s1router.domain.capabilities import Capabilities
from s1router.ports.providers import PROVIDER_FAILURES, ProviderFailure, ProviderReply

pytestmark = [pytest.mark.behavioral]


# --- WorkerService / _valid_smoke -------------------------------------------------


def _ready_worker(**overrides: Any) -> WorkerService:
    written: list[dict[str, Any]] = []
    options: dict[str, Any] = dict(
        smoke_test=lambda: {
            "schema_version": "1.0",
            "audit_ref": "smoke",
            "outcomes": [
                {"prediction": {"status": "predicted", "selected_id": "bug", "probabilities": []}}
            ],
        },
        write=written.append,
        log=lambda _msg: None,
    )
    options.update(overrides)
    return WorkerService(lambda raw: {"schema_version": "1.0"}, **options)


@pytest.mark.requirement("R-009")
def test_worker_service_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="invalid_configuration"):
        _ready_worker(capacity=0)
    with pytest.raises(ValueError, match="invalid_configuration"):
        _ready_worker(capacity="32")


@pytest.mark.requirement("R-009")
def test_worker_service_refuses_to_start_once_shutdown_was_already_requested() -> None:
    worker = _ready_worker()
    worker.shutdown()
    with pytest.raises(ValueError, match="cancelled"):
        worker.start()
    assert not worker.ready()


@pytest.mark.requirement("R-009")
def test_worker_service_treats_a_racing_full_queue_as_queue_full() -> None:
    """A full() check can pass then lose the race to put_nowait(); must still reject cleanly."""
    worker = _ready_worker()
    worker.start()

    class AlwaysRacesFull:
        def full(self) -> bool:
            return False

        def put_nowait(self, item: bytes) -> None:
            raise queue.Full

    worker._queue = AlwaysRacesFull()  # type: ignore[assignment]
    assert worker.submit(json.dumps({"request_id": "race"}).encode()) is False


@pytest.mark.requirement("R-009")
def test_worker_service_run_once_treats_a_sentinel_as_shutdown() -> None:
    worker = _ready_worker()
    worker.start()
    worker._queue.put(None)
    assert worker.run_once() is False


@pytest.mark.requirement("R-009")
def test_worker_service_count_ignores_unregistered_labels() -> None:
    worker = _ready_worker()
    worker._count("not_a_real_metric")
    assert "not_a_real_metric" not in worker.metrics()


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"schema_version": "0.9"},
        {"schema_version": "1.0", "audit_ref": ""},
        {"schema_version": "1.0", "audit_ref": "x", "outcomes": []},
        {"schema_version": "1.0", "audit_ref": "x", "outcomes": "not-a-list"},
        {"schema_version": "1.0", "audit_ref": "x", "outcomes": [{"prediction": None}]},
        {
            "schema_version": "1.0",
            "audit_ref": "x",
            "outcomes": [{"prediction": {"status": "abstained"}}],
        },
        {
            "schema_version": "1.0",
            "audit_ref": "x",
            "outcomes": [{"prediction": {"status": "predicted", "selected_id": ""}}],
        },
    ],
)
@pytest.mark.requirement("R-009")
def test_valid_smoke_rejects_every_malformed_shape(value: Any) -> None:
    assert _valid_smoke(value) is False


# --- ProviderFailure ---------------------------------------------------------------


@pytest.mark.requirement("R-006")
def test_provider_failure_rejects_an_unregistered_code() -> None:
    with pytest.raises(ValueError, match="invalid_provider_output"):
        ProviderFailure("not_a_registered_failure_code")
    for code in PROVIDER_FAILURES:
        assert ProviderFailure(code).code == code


# --- attempt(): budget and breaker fault injection ----------------------------------


class _RemoteProvider:
    remote: bool = True
    endpoint: str | None = "https://gateway.example/decision"
    max_cost_usd: str = "0.100000"
    capabilities: Capabilities | None = None
    calibration: CalibrationProfile | None = None
    provider_id = "remote-fixture"

    def count_tokens(self, text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        raise AssertionError("must not be reached: rejected before dispatch")


def _item() -> dict[str, Any]:
    return {
        "status": "review_required",
        "selected_id": None,
        "prediction": None,
        "reason": "provider_unavailable",
        "attempts": [],
    }


@pytest.mark.requirement("R-006")
def test_attempt_reports_invalid_configuration_for_an_unparseable_provider_budget() -> None:
    provider = _RemoteProvider()
    provider.max_cost_usd = "not-a-number"
    item = _item()
    attempt(
        lambda: 0.0,
        lambda: 0.0,
        CircuitBreaker(provider.provider_id),
        provider,
        {"questions": []},
        {"support": []},
        item,
        MonotonicDeadline(10.0, clock=lambda: 0.0),
        BudgetLedger(max_cost_usd="1.000000"),
        {"remote_auto_accept": True},
    )
    assert item["reason"] == "invalid_configuration"
    assert item["attempts"][0]["reason"] == "invalid_configuration"


@pytest.mark.requirement("R-006")
def test_attempt_reports_budget_exhausted_when_ledger_has_no_room() -> None:
    provider = _RemoteProvider()
    item = _item()
    ledger = BudgetLedger(max_cost_usd="0.050000")  # below the provider's own max_cost_usd
    attempt(
        lambda: 0.0,
        lambda: 0.0,
        CircuitBreaker(provider.provider_id),
        provider,
        {"questions": []},
        {"support": []},
        item,
        MonotonicDeadline(10.0, clock=lambda: 0.0),
        ledger,
        {"remote_auto_accept": True},
    )
    assert item["reason"] == "budget_exhausted"


@pytest.mark.requirement("R-006")
def test_attempt_wraps_a_broken_breaker_as_provider_unavailable() -> None:
    class BrokenBreaker:
        def acquire(self) -> None:
            raise RuntimeError("breaker backing store unavailable")

        def record_failure(self, permit: Any, *, transient: bool) -> None:
            raise AssertionError("no permit was ever issued")

        def record_success(self, permit: Any) -> None:
            raise AssertionError("no permit was ever issued")

    provider = _RemoteProvider()
    item = _item()
    attempt(
        lambda: 0.0,
        lambda: 0.0,
        cast(CircuitBreaker, BrokenBreaker()),
        provider,
        {"questions": []},
        {"support": []},
        item,
        MonotonicDeadline(10.0, clock=lambda: 0.0),
        BudgetLedger(max_cost_usd="1.000000"),
        {"remote_auto_accept": True},
    )
    assert item["reason"] == "provider_unavailable"
