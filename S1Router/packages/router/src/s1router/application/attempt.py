"""One bounded provider attempt with conservative cost settlement."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from s1_contracts.prediction import validate_prediction
from s1router.application.breaker import CircuitBreaker, CircuitPermit
from s1router.application.budget import BudgetLedger, MonotonicDeadline
from s1router.application.clock import finite_time
from s1router.domain.acceptance import accept
from s1router.ports.providers import DecisionProvider, ProviderFailure


def money(micros: int) -> str:
    return f"{micros // 1_000_000}.{micros % 1_000_000:06d}"


def _elapsed_ms(clock: Callable[[], float], started: float | None) -> float:
    if started is None:
        return 0.0
    try:
        return max(0.0, (finite_time(clock()) - started) * 1000.0)
    except Exception:
        return 0.0


def _record_failure(breaker: CircuitBreaker, permit: CircuitPermit, *, transient: bool) -> None:
    try:
        breaker.record_failure(permit, transient=transient)
    except Exception:
        pass


def attempt(
    clock: Callable[[], float],
    wall_clock: Callable[[], float],
    breaker: CircuitBreaker,
    provider: DecisionProvider,
    request: dict[str, Any],
    question: dict[str, Any],
    item: dict[str, Any],
    deadline: MonotonicDeadline,
    ledger: BudgetLedger,
    config: dict[str, Any],
) -> None:
    ticket = None
    permit = None
    dispatched = False
    charged = 0
    started = None
    try:
        if provider.remote:
            try:
                ticket = ledger.reserve(provider.max_cost_usd)
            except ValueError:
                item["reason"] = "invalid_configuration"
                return
            if ticket is None:
                item["reason"] = "budget_exhausted"
                return
        try:
            permit = breaker.acquire()
        except Exception as exc:
            raise RuntimeError("breaker admission failed") from exc
        if permit is None:
            item["reason"] = "provider_unavailable"
            return
        try:
            started = finite_time(clock())
        except Exception as exc:
            raise RuntimeError("invalid attempt clock") from exc
        deadline.ensure_remaining()
        if ticket is not None:
            ledger.dispatch(ticket)
        dispatched = True
        reply = provider.evaluate(
            copy.deepcopy(request), copy.deepcopy(question), deadline.remaining_seconds()
        )
        if ticket is not None:
            charged = ledger.settle(ticket, reply.actual_cost_usd)
            ticket = None
        deadline.ensure_remaining()
        prediction = (
            validate_prediction(reply.prediction, question)
            if reply.prediction is not None
            else None
        )
        if provider.remote:
            if prediction is not None:
                selected = prediction["selected_id"]
                if accept(question, prediction, provider.calibration, now=wall_clock()) is not None:
                    prediction = None
            else:
                selected = reply.selected_id
            if not isinstance(selected, str) or selected not in {
                entry["id"] for entry in question["support"]
            }:
                raise ValueError("invalid_provider_output")
            reason = None if config["remote_auto_accept"] else "mandatory_review"
            status = "answered_remote"
        else:
            if prediction is None:
                raise ValueError("invalid_provider_output")
            selected = prediction["selected_id"]
            reason = accept(question, prediction, provider.calibration, now=wall_clock())
            status = "answered_local"
        item.update(
            status=status if reason is None else "review_required",
            selected_id=selected if reason is None else None,
            prediction=prediction,
            reason=reason,
        )
        breaker.record_success(permit)
        permit = None
    except ProviderFailure as exc:
        item.update(status="review_required", selected_id=None, prediction=None, reason=exc.code)
        if permit is not None:
            _record_failure(breaker, permit, transient=exc.transient)
            permit = None
    except TimeoutError:
        item["reason"] = "deadline_exceeded"
        if permit is not None:
            _record_failure(breaker, permit, transient=True)
            permit = None
    except ValueError:
        item["reason"] = "invalid_provider_output"
        if permit is not None:
            _record_failure(breaker, permit, transient=False)
            permit = None
    except Exception:
        item["reason"] = "provider_unavailable"
        if permit is not None:
            _record_failure(breaker, permit, transient=True)
            permit = None
    finally:
        if ticket is not None:
            try:
                if dispatched:
                    charged = ledger.settle(ticket)
                else:
                    ledger.cancel(ticket)
            except Exception:
                pass
        if permit is not None:
            _record_failure(breaker, permit, transient=False)
        item["attempts"].append(
            dict(
                provider_id=provider.provider_id,
                status=item["status"],
                reason=item["reason"],
                elapsed_ms=_elapsed_ms(clock, started),
                cost_usd=money(charged),
            )
        )
