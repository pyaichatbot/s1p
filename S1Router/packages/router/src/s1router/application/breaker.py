"""Per-provider circuit breaker with a single half-open probe."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from s1router.application.clock import finite_time

Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class CircuitPermit:
    """Opaque admission capability bound to one breaker generation."""

    _token: int
    _generation: int
    _probe: bool


class CircuitBreaker:
    """Thread-safe closed/open/half-open provider health state."""

    def __init__(
        self,
        provider_id: str,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        clock: Clock = time.monotonic,
    ) -> None:
        if not isinstance(provider_id, str) or not provider_id:
            raise ValueError("invalid provider id")
        if isinstance(failure_threshold, bool) or not isinstance(failure_threshold, int):
            raise ValueError("invalid failure threshold")
        if failure_threshold < 1:
            raise ValueError("invalid failure threshold")
        if isinstance(cooldown_seconds, bool):
            raise ValueError("invalid cooldown")
        try:
            cooldown = finite_time(float(cooldown_seconds), "cooldown")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid cooldown") from exc
        if cooldown <= 0:
            raise ValueError("invalid cooldown")
        now = finite_time(clock())
        self.provider_id = provider_id
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown
        self._clock = clock
        self._last_now = now
        self._state = "closed"
        self._failures = 0
        self._open_until = 0.0
        self._probe_in_flight = False
        self._generation = 0
        self._next_token = 1
        self._active: dict[int, CircuitPermit] = {}
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            self._refresh_locked()
            return self._state

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._failures

    def acquire(self) -> CircuitPermit | None:
        """Atomically admit a request or the one half-open probe."""
        with self._lock:
            now = self._refresh_locked()
            if self._state == "closed":
                return self._new_permit(False)
            if self._state == "open":
                return None
            if self._probe_in_flight:
                return None
            self._probe_in_flight = True
            self._open_until = now
            return self._new_permit(True)

    allow_request = acquire
    before_call = acquire

    def record_success(self, permit: CircuitPermit) -> bool:
        with self._lock:
            self._refresh_locked()
            if not self._complete(permit):
                return False
            if self._state == "open":
                return True
            self._state = "closed"
            self._failures = 0
            self._probe_in_flight = False
            self._open_until = 0.0
            return True

    on_success = record_success

    def record_failure(self, permit: CircuitPermit, transient: bool = True) -> bool:
        """Record a failure; permanent or policy failures do not trip health."""
        if not isinstance(transient, bool):
            raise ValueError("invalid transient flag")
        with self._lock:
            now = self._refresh_locked()
            if not self._complete(permit):
                return False
            if self._state == "open":
                return True
            if not transient:
                self._probe_in_flight = False
                return True
            if self._state == "half_open":
                self._open(now)
                return True
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._open(now)
            return True

    on_failure = record_failure

    def reset(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._open_until = 0.0
            self._probe_in_flight = False
            self._generation += 1
            self._active.clear()

    def _new_permit(self, probe: bool) -> CircuitPermit:
        permit = CircuitPermit(self._next_token, self._generation, probe)
        self._next_token += 1
        self._active[permit._token] = permit
        return permit

    def _complete(self, permit: CircuitPermit) -> bool:
        if not isinstance(permit, CircuitPermit):
            return False
        current = self._active.get(permit._token)
        if current is not permit or permit._generation != self._generation:
            return False
        del self._active[permit._token]
        return True

    def _now(self) -> float:
        now = finite_time(self._clock())
        self._last_now = max(self._last_now, now)
        return self._last_now

    def _refresh_locked(self) -> float:
        now = self._now()
        if self._state == "open" and now >= self._open_until:
            self._state = "half_open"
            self._probe_in_flight = False
            self._generation += 1
            self._active.clear()
        return now

    def _open(self, now: float) -> None:
        self._state = "open"
        self._open_until = now + self.cooldown_seconds
        self._probe_in_flight = False
        self._generation += 1
        self._active.clear()

    def snapshot(self) -> dict[str, float | int | str | bool]:
        with self._lock:
            now = self._refresh_locked()
            return {
                "provider_id": self.provider_id,
                "state": self._state,
                "consecutive_failures": self._failures,
                "cooldown_remaining_seconds": max(0.0, self._open_until - now),
                "probe_in_flight": self._probe_in_flight,
            }
