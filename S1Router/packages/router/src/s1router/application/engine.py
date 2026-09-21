"""SDK orchestration: immutable policy, finite attempts, isolated outcomes and audit."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from s1_contracts.request import parse_request
from s1router.application.attempt import attempt, money
from s1router.application.breaker import CircuitBreaker
from s1router.application.budget import BudgetLedger, MonotonicDeadline, parse_microdollars
from s1router.domain.capabilities import RegisteredTask
from s1router.domain.policy import PolicySnapshot
from s1router.ports.providers import AuditSink, DecisionProvider


def outcome(question: dict[str, Any]) -> dict[str, Any]:
    return dict(
        question_id=question["id"],
        status="review_required",
        selected_id=None,
        prediction=None,
        reason="provider_unavailable",
        attempts=[],
    )


class Router:
    def __init__(
        self,
        policy: PolicySnapshot,
        providers: tuple[DecisionProvider, ...],
        tasks: tuple[RegisteredTask, ...],
        audit: AuditSink,
        *,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.policy, self.tasks, self.audit = policy, tuple(tasks), audit
        self.providers = {provider.provider_id: provider for provider in providers}
        if len(self.providers) != len(providers) or any(
            name not in self.providers for name in policy.config["providers"]
        ):
            raise ValueError("invalid_configuration")
        self.clock, self.wall_clock = clock, wall_clock
        self.breakers = {name: CircuitBreaker(name, clock=clock) for name in self.providers}

    def decide(self, raw: bytes) -> dict[str, Any]:
        request = parse_request(raw)
        policy = self.policy
        config = policy.config
        started = self.clock()
        deadline = MonotonicDeadline.from_timeout_ms(
            min(config["deadline_ms"], request["constraints"]["deadline_ms"]), clock=self.clock
        )
        ceiling = min(
            parse_microdollars(config["max_cost_usd"]),
            parse_microdollars(request["constraints"]["max_cost_usd"]),
        )
        ledger = BudgetLedger(limit_microdollars=ceiling)
        results = [
            self._question(request, q, policy, deadline, ledger) for q in request["questions"]
        ]
        elapsed = max(0, self.clock() - started) * 1000
        registry = hashlib.sha256(
            "".join(sorted(task.reference for task in self.tasks)).encode()
        ).hexdigest()
        result = dict(
            schema_version="1.0",
            request_id=request["request_id"],
            policy_ref=policy.reference,
            task_registry_ref=registry,
            outcomes=results,
            timings_ms={"processing": elapsed},
            cost_usd=money(ledger.spent_microdollars),
            audit_ref=None,
        )
        record = dict(
            schema_version="1.0",
            policy_ref=policy.reference,
            task_registry_ref=registry,
            input_sha256=hashlib.sha256(raw).hexdigest(),
            cost_usd=result["cost_usd"],
            duration_ms=elapsed,
            outcomes=[
                dict(index=i, status=o["status"], reason=o["reason"]) for i, o in enumerate(results)
            ],
        )
        try:
            reference = self.audit.append(record)
            if not isinstance(reference, str) or not reference:
                raise OSError("invalid audit reference")
            result["audit_ref"] = reference
        except OSError:
            for item in results:
                item.update(
                    status="review_required",
                    selected_id=None,
                    prediction=None,
                    reason="audit_unavailable",
                )
        return result

    def _question(
        self,
        request: dict[str, Any],
        question: dict[str, Any],
        policy: PolicySnapshot,
        deadline: MonotonicDeadline,
        ledger: BudgetLedger,
    ) -> dict[str, Any]:
        item = outcome(question)
        config = policy.config
        if question["task_id"] in config["mandatory_review_tasks"]:
            item["reason"] = "mandatory_review"
            return item
        if deadline.expired():
            item["reason"] = "deadline_exceeded"
            return item
        task = next((task for task in self.tasks if task.matches(question, request["state"])), None)
        if task is not None and request["language"] in task.definition["languages"]:
            selected, reason, rule = policy.rule(question, request["state"])
            if selected is not None or reason is not None:
                item.update(
                    selected_id=selected,
                    reason=reason,
                    status="answered_rule" if selected else "review_required",
                )
                item["attempts"].append(
                    dict(
                        rule_ref=rule,
                        status=item["status"],
                        reason=reason,
                        elapsed_ms=0.0,
                        cost_usd="0.000000",
                    )
                )
                return item
        for name in config["providers"]:
            if deadline.expired():
                item["reason"] = "deadline_exceeded"
                break
            provider = self.providers[name]
            reason = self._permission(provider, request, question, config)
            if reason is not None:
                item["reason"] = reason
                continue
            attempt(
                self.clock,
                self.wall_clock,
                self.breakers[name],
                provider,
                request,
                question,
                item,
                deadline,
                ledger,
                config,
            )
            if item["status"].startswith("answered_"):
                break
        return item

    def _permission(
        self,
        provider: DecisionProvider,
        request: dict[str, Any],
        question: dict[str, Any],
        config: dict[str, Any],
    ) -> str | None:
        if provider.remote:
            if not config["allow_remote"] or not request["constraints"]["allow_remote"]:
                return "remote_disabled"
            if (
                provider.endpoint not in config["allowed_endpoints"]
                or request["data_class"] not in config["allowed_data_classes"]
            ):
                return "data_policy"
            return None
        if provider.capabilities is None:
            return "unsupported_task"
        try:
            return provider.capabilities.check(request, question, provider.count_tokens)
        except Exception:
            return "provider_unavailable"
