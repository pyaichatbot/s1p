"""R-013: measured router overhead -- the routing/acceptance-gating logic's
own added latency, isolated from provider/model inference time.

The drill runs the real ``Router.decide()`` core decision path many times
against a deterministic fake local provider that does zero simulated work
(no sleep, no I/O, no network), so any measured wall-clock time is entirely
the router's own admission, budget, breaker, acceptance-gating and audit
bookkeeping -- not inference. It reports a real, executable measurement via
``time.perf_counter()`` and asserts it stays under a documented, generous
budget, so a severe regression (an accidental O(n^2) pass, a busy-wait, a
runaway retry loop) would fail the suite, while ordinary machine noise does
not produce a flaky failure.

Reuses the ``FlakyLocalProvider``/``FakeClock`` test doubles already defined
for the R-013 outage/rollback drills, rather than inventing a parallel one.
"""

from __future__ import annotations

import json
import time
from statistics import median

import pytest
from s1_contracts.request import example_request
from s1router.application.engine import Router
from s1router.domain.policy import PolicySnapshot, default_policy
from test_provider_outage_and_rollback import Audit, FakeClock, FlakyLocalProvider, _task

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]

#: Wall-clock time budget per Router.decide() call, in milliseconds.
#:
#: This is deliberately generous, not a tight SLA: it is pure in-process
#: Python logic (policy lookup, budget/breaker bookkeeping, JSON parsing of
#: a tiny request, one dict-audit append) with zero real I/O and zero
#: simulated provider latency in this drill. On ordinary developer/CI
#: hardware this consistently measures under 2ms; 50ms leaves roughly a
#: 25x margin so the assertion catches an actual severe regression (a
#: runaway loop, an accidental O(n^2) pass, a busy-wait) instead of flaking
#: on shared/loaded CI runners.
MAX_MEDIAN_OVERHEAD_MS = 50.0
ITERATIONS = 200


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

    overhead = median(samples)
    assert overhead < MAX_MEDIAN_OVERHEAD_MS, (
        f"router overhead regressed: median {overhead:.3f}ms over {ITERATIONS} calls "
        f"exceeds the {MAX_MEDIAN_OVERHEAD_MS}ms budget for pure in-process routing logic"
    )
