"""Behavioral evidence for bounded remote execution controls."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from s1router.application.breaker import CircuitBreaker
from s1router.application.budget import BudgetLedger, MonotonicDeadline, SettlementError

pytestmark = [pytest.mark.behavioral]


class FakeClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


@pytest.mark.requirement("R-006")
def test_budget_reservation_is_atomic_under_concurrency() -> None:
    ledger = BudgetLedger(max_cost_usd="5.000000")
    barrier = Barrier(20)

    def reserve() -> object:
        barrier.wait()
        return ledger.reserve("1.000000")

    with ThreadPoolExecutor(max_workers=20) as pool:
        tickets = list(pool.map(lambda _: reserve(), range(20)))

    accepted = [ticket for ticket in tickets if ticket is not None]
    assert len(accepted) == 5
    assert ledger.reserved_microdollars == 5_000_000
    assert ledger.available_microdollars == 0


@pytest.mark.requirement("R-006")
def test_budget_settlement_and_cancellation_are_single_use() -> None:
    ledger = BudgetLedger(max_cost_usd="2.000000")
    released = ledger.reserve("0.750000")
    assert released is not None
    ledger.cancel(released)
    assert ledger.available_microdollars == 2_000_000
    with pytest.raises(ValueError, match="ticket"):
        ledger.cancel(released)

    known = ledger.reserve("0.750000")
    assert known is not None
    ledger.dispatch(known)
    assert ledger.settle(known, actual_cost_usd="0.250000") == 250_000
    assert ledger.spent_microdollars == 250_000
    with pytest.raises(ValueError, match="ticket"):
        ledger.settle(known, actual_cost_usd="0.100000")

    unknown = ledger.reserve("0.500000")
    assert unknown is not None
    ledger.dispatch(unknown)
    ledger.settle(unknown)
    assert ledger.spent_microdollars == 750_000
    assert ledger.reserved_microdollars == 0


@pytest.mark.requirement("R-006")
def test_budget_rejects_bad_values_without_mutating_accounting() -> None:
    assert BudgetLedger(max_cost_usd="0.000000").reserve("0.000001") is None
    for value in ("-0.000001", "1.0000001", "NaN", "not-money", 1.5, True):
        with pytest.raises(ValueError):
            BudgetLedger(max_cost_usd=value)

    ledger = BudgetLedger(max_cost_usd="1.000000")
    ticket = ledger.reserve("0.500000")
    assert ticket is not None
    ledger.dispatch(ticket)
    before = ledger.snapshot()
    with pytest.raises(SettlementError):
        ledger.settle(ticket, actual_cost_usd="0.600000")
    assert ledger.snapshot() == before
    assert ledger.reserve("0.500000") is None


@pytest.mark.requirement("R-006")
def test_deadline_uses_injected_monotonic_clock_at_boundary() -> None:
    clock = FakeClock(10.0)
    deadline = MonotonicDeadline.from_timeout_ms(100, clock=clock)
    assert not deadline.expired()
    assert deadline.remaining_ms() == 100
    clock.value = 10.099
    assert deadline.remaining_ms() == 1
    clock.value = 10.1
    assert deadline.expired()
    assert deadline.remaining_ms() == 0


@pytest.mark.requirement("R-011")
def test_breaker_transitions_closed_open_half_open_and_closes_on_probe() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("gateway", clock=clock)
    for _ in range(4):
        permit = breaker.acquire()
        assert permit is not None
        assert breaker.record_failure(permit)
    assert breaker.state == "closed"
    permit = breaker.acquire()
    assert permit is not None
    assert breaker.record_failure(permit)
    assert breaker.state == "open"
    assert not breaker.allow_request()
    clock.value = 30.0
    assert breaker.state == "half_open"
    permit = breaker.acquire()
    assert permit is not None
    assert breaker.acquire() is None
    assert breaker.record_success(permit)
    assert breaker.state == "closed"
    assert breaker.acquire() is not None


@pytest.mark.requirement("R-011")
def test_breaker_allows_only_one_concurrent_half_open_probe() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("gateway", clock=clock, failure_threshold=1)
    permit = breaker.acquire()
    assert permit is not None
    breaker.record_failure(permit)
    clock.value = 30.0
    barrier = Barrier(12)

    def probe() -> object:
        barrier.wait()
        return breaker.allow_request()

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: probe(), range(12)))
    assert sum(result is not None for result in results) == 1


@pytest.mark.requirement("R-011")
def test_breaker_ignores_late_completion_and_releases_nontransient_probe() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker("gateway", clock=clock, failure_threshold=1)
    first = breaker.acquire()
    assert first is not None
    assert breaker.record_failure(first)
    clock.value = 30.0
    probe = breaker.acquire()
    assert probe is not None
    assert breaker.record_success(first) is False
    assert breaker.state == "half_open"
    assert breaker.record_failure(probe, transient=False)
    assert breaker.acquire() is not None


@pytest.mark.requirement("R-011")
def test_breaker_rejects_invalid_numeric_configuration() -> None:
    with pytest.raises(ValueError):
        CircuitBreaker("gateway", failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker("gateway", cooldown_seconds=0)
    with pytest.raises(ValueError):
        CircuitBreaker("gateway", cooldown_seconds=float("nan"))
    with pytest.raises(ValueError):
        CircuitBreaker("gateway", failure_threshold=True)


@pytest.mark.requirement("R-011")
def test_forged_permit_cannot_consume_the_real_probe() -> None:
    from dataclasses import replace

    clock = FakeClock()
    breaker = CircuitBreaker("gateway", clock=clock, failure_threshold=1)
    initial = breaker.acquire()
    assert initial is not None
    breaker.record_failure(initial)
    clock.value = 30
    probe = breaker.acquire()
    assert probe is not None
    assert not breaker.record_success(replace(probe))
    assert breaker.acquire() is None
    assert breaker.record_success(probe)
    assert breaker.state == "closed"


@pytest.mark.requirement("R-006")
@pytest.mark.requirement("R-011")
@pytest.mark.parametrize("invalid", [True, "1", None, float("inf"), 10**400])
def test_invalid_clock_values_fail_closed(invalid: object) -> None:
    from collections.abc import Callable
    from typing import cast

    clock = cast(Callable[[], float], lambda: invalid)
    with pytest.raises(ValueError, match="clock"):
        CircuitBreaker("gateway", clock=clock)
    with pytest.raises(ValueError, match="clock"):
        MonotonicDeadline.from_timeout_ms(100, clock=clock)


@pytest.mark.requirement("R-006")
def test_deadline_rejects_overflow_without_unhandled_numeric_error() -> None:
    with pytest.raises(ValueError, match="deadline"):
        MonotonicDeadline(10**400)
    with pytest.raises(ValueError, match="deadline"):
        MonotonicDeadline.from_timeout_ms(10**400)


@pytest.mark.requirement("R-006")
@pytest.mark.requirement("R-011")
def test_time_bounds_reject_values_that_overflow_runtime_arithmetic() -> None:
    with pytest.raises(ValueError, match="deadline"):
        MonotonicDeadline(1e308, clock=lambda: 0.0)
    with pytest.raises(ValueError, match="cooldown"):
        CircuitBreaker("gateway", cooldown_seconds=1e308, clock=lambda: 0.0)
