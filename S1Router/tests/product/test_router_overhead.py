"""R-013 router-only single-question latency gate; not model quality evidence."""

from __future__ import annotations

import json
import platform
import time

import pytest
from s1_contracts.request import example_request
from s1router.application.engine import Router
from s1router.domain.policy import PolicySnapshot, default_policy
from test_provider_outage_and_rollback import Audit, FakeClock, FlakyLocalProvider, _task

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]

MAX_P95_OVERHEAD_MS = 10.0
ITERATIONS = 10_000


def _router() -> Router:
    provider = FlakyLocalProvider(example_request()["questions"][0])
    config = default_policy() | {"providers": ["local"]}
    return Router(
        PolicySnapshot.from_dict(config),
        (provider,),
        (_task(),),
        Audit(),
        clock=FakeClock(),
        wall_clock=lambda: 100.0,
    )


def measure_decide_overhead_ms(router: Router, raw: bytes, iterations: int) -> list[float]:
    """Return the per-call wall-clock duration, in milliseconds, of ``iterations``
    calls to ``router.decide(raw)`` against a zero-latency fake provider."""
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        router.decide(raw)
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


@pytest.mark.requirement("R-013")
def test_router_decision_path_overhead_stays_within_budget() -> None:
    router = _router()
    raw = json.dumps(example_request()).encode()

    measure_decide_overhead_ms(router, raw, 5)  # warm up interpreter/import caches
    samples = measure_decide_overhead_ms(router, raw, ITERATIONS)

    ordered = sorted(samples)
    p95 = ordered[int(0.95 * ITERATIONS) - 1]
    measurement = {
        "iterations": ITERATIONS,
        "concurrency": 1,
        "payload": "example_request: one Choice question; identical input each call",
        "payload_bytes": len(raw),
        "machine": platform.platform(),
        "python": platform.python_version(),
        "provider": "zero-work fake",
        "warmup_calls": 5,
        "p50_ms": ordered[ITERATIONS // 2 - 1],
        "p95_ms": p95,
        "p99_ms": ordered[int(0.99 * ITERATIONS) - 1],
    }
    print(json.dumps(measurement, sort_keys=True))
    assert p95 <= MAX_P95_OVERHEAD_MS, measurement
