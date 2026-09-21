"""Process-local token bucket; the resident runtime owns its lifetime."""

from __future__ import annotations

import math
from collections.abc import Callable


class TokenBucket:
    def __init__(self, rate: float, burst: int, clock: Callable[[], float]) -> None:
        if not math.isfinite(rate) or rate <= 0 or type(burst) is not int or burst < 1:
            raise ValueError("invalid_configuration")
        self.rate = rate
        self.burst = burst
        self.clock = clock
        self.tokens = float(burst)
        self.last = clock()

    def allow(self) -> bool:
        now = self.clock()
        elapsed = max(0.0, now - self.last)
        self.last = max(now, self.last)
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
        if self.tokens < 1 - 1e-12:
            return False
        self.tokens = max(0.0, self.tokens - 1)
        return True
