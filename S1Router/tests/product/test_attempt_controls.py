"""Behavioral evidence for per-attempt budget and cleanup accounting."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
from s1router.application.attempt import attempt
from s1router.application.breaker import CircuitBreaker
from s1router.application.budget import BudgetLedger, MonotonicDeadline
from s1router.domain.acceptance import CalibrationProfile
from s1router.domain.capabilities import Capabilities
from s1router.ports.providers import ProviderReply

pytestmark = [pytest.mark.behavioral]


def _item() -> dict[str, Any]:
    return {
        "status": "review_required",
        "selected_id": None,
        "prediction": None,
        "reason": "provider_unavailable",
        "attempts": [],
    }


class RemoteProvider:
    remote: bool = True
    endpoint: str | None = "https://gateway.example/decision"
    max_cost_usd: str = "0.100000"
    capabilities: Capabilities | None = None
    calibration: CalibrationProfile | None = None

    def __init__(self, provider_id: str, barrier: Barrier | None = None) -> None:
        self.provider_id = provider_id
        self.barrier = barrier

    def count_tokens(self, text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        if self.barrier is not None:
            self.barrier.wait()
        return ProviderReply(selected_id="bug", actual_cost_usd="0.100000")


class InvalidAcquireClock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return 0.0 if self.calls == 1 else float("nan")


class FailingElapsedClock:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        if self.calls == 1:
            return 0.0
        raise ValueError("invalid cleanup clock")


class RaisingClock:
    def __call__(self) -> float:
        raise ValueError("invalid start clock")


class TimeoutProvider(RemoteProvider):
    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        raise TimeoutError("provider timed out")


def _run_attempt(
    provider: RemoteProvider,
    breaker: CircuitBreaker,
    ledger: BudgetLedger,
    deadline: MonotonicDeadline,
    *,
    clock: Any = lambda: 0.0,
) -> dict[str, Any]:
    item = _item()
    attempt(
        clock,
        lambda: 0.0,
        breaker,
        provider,
        {},
        {"support": [{"id": "bug"}]},
        item,
        deadline,
        ledger,
        {"remote_auto_accept": False},
    )
    return item


@pytest.mark.requirement("R-006")
def test_settlement_cleanup_releases_budget_when_breaker_clock_fails() -> None:
    breaker_clock = InvalidAcquireClock()
    ledger = BudgetLedger(max_cost_usd="1.000000")
    deadline = MonotonicDeadline.from_timeout_ms(1000, clock=lambda: 0.0)
    item = _run_attempt(
        RemoteProvider("gateway"),
        CircuitBreaker("gateway", clock=breaker_clock),
        ledger,
        deadline,
    )
    assert item["reason"] == "provider_unavailable"
    assert len(item["attempts"]) == 1
    assert ledger.reserved_microdollars == 0


@pytest.mark.requirement("R-006")
def test_cleanup_clock_failure_does_not_mask_provider_timeout() -> None:
    ledger = BudgetLedger(max_cost_usd="1.000000")
    deadline = MonotonicDeadline.from_timeout_ms(1000, clock=lambda: 0.0)
    item = _run_attempt(
        TimeoutProvider("gateway"),
        CircuitBreaker("gateway", clock=lambda: 0.0),
        ledger,
        deadline,
        clock=FailingElapsedClock(),
    )
    assert item["reason"] == "deadline_exceeded"
    assert item["attempts"][0]["elapsed_ms"] == 0.0
    assert ledger.reserved_microdollars == 0
    assert ledger.spent_microdollars == 100_000


@pytest.mark.requirement("R-006")
def test_start_clock_failure_releases_reservation_and_permit() -> None:
    ledger = BudgetLedger(max_cost_usd="1.000000")
    deadline = MonotonicDeadline.from_timeout_ms(1000, clock=lambda: 0.0)
    item = _run_attempt(
        RemoteProvider("gateway"),
        CircuitBreaker("gateway", clock=lambda: 0.0),
        ledger,
        deadline,
        clock=RaisingClock(),
    )
    assert item["reason"] == "provider_unavailable"
    assert len(item["attempts"]) == 1
    assert ledger.reserved_microdollars == 0


@pytest.mark.requirement("R-006")
def test_concurrent_attempts_report_ticket_local_costs() -> None:
    barrier = Barrier(2)
    ledger = BudgetLedger(max_cost_usd="1.000000")
    deadline = MonotonicDeadline.from_timeout_ms(1000, clock=lambda: 0.0)
    providers = [RemoteProvider("one", barrier), RemoteProvider("two", barrier)]

    def run(provider: RemoteProvider) -> dict[str, Any]:
        return _run_attempt(
            provider,
            CircuitBreaker(provider.provider_id, clock=lambda: 0.0),
            ledger,
            deadline,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        items = list(pool.map(run, providers))

    assert sorted(item["attempts"][0]["cost_usd"] for item in items) == [
        "0.100000",
        "0.100000",
    ]
    assert ledger.spent_microdollars == 200_000


@pytest.mark.requirement("R-006")
def test_completion_failure_cannot_leave_an_automatic_answer() -> None:
    class BrokenCompletion(CircuitBreaker):
        def record_success(self, permit: Any) -> bool:
            raise RuntimeError("completion failed")

    item = _item()
    attempt(
        lambda: 0.0,
        lambda: 0.0,
        BrokenCompletion("gateway", clock=lambda: 0.0),
        RemoteProvider("gateway"),
        {},
        {"support": [{"id": "bug"}]},
        item,
        MonotonicDeadline.from_timeout_ms(1000, clock=lambda: 0.0),
        BudgetLedger(max_cost_usd="1.000000"),
        {"remote_auto_accept": True},
    )
    assert item["status"] == "review_required"
    assert item["selected_id"] is None
    assert item["prediction"] is None
    assert item["reason"] == "provider_unavailable"
