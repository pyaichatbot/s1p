"""Thread-safe request cost reservations and monotonic execution deadlines."""

from __future__ import annotations

import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation

from s1router.application.clock import finite_time

_USD = re.compile(r"(?:0|[1-9]\d*)(?:\.\d{1,6})?\Z")
Clock = Callable[[], float]


class BudgetError(ValueError):
    """Base error for budget accounting violations."""


class SettlementError(BudgetError):
    """Reported cost cannot be settled against its reservation."""


def parse_microdollars(value: object, *, allow_zero: bool = True) -> int:
    """Parse an exact USD amount into integer microdollars."""
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise ValueError("invalid monetary value")
    if isinstance(value, int):
        if value < 0 or (value == 0 and not allow_zero):
            raise ValueError("invalid monetary value")
        return value * 1_000_000
    text = str(value) if isinstance(value, str) else format(value, "f")
    if not _USD.fullmatch(text):
        raise ValueError("invalid monetary value")
    try:
        amount = Decimal(text).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid monetary value") from exc
    micros = int(amount * 1_000_000)
    if micros == 0 and not allow_zero:
        raise ValueError("amount must be positive")
    return micros


@dataclass(frozen=True, slots=True)
class Reservation:
    """Opaque capability returned for one reservation."""

    ticket_id: int
    reserved_microdollars: int

    @property
    def id(self) -> int:
        return self.ticket_id


@dataclass(slots=True)
class _Entry:
    ticket: Reservation
    state: str = "reserved"


class BudgetLedger:
    """An atomic per-request budget ledger with conservative settlement."""

    def __init__(
        self,
        max_cost_usd: object | None = None,
        *,
        limit_microdollars: int | None = None,
    ) -> None:
        if (max_cost_usd is None) == (limit_microdollars is None):
            raise ValueError("provide exactly one budget limit")
        if limit_microdollars is not None:
            if (
                isinstance(limit_microdollars, bool)
                or not isinstance(limit_microdollars, int)
                or limit_microdollars < 0
            ):
                raise ValueError("invalid budget limit")
            limit = limit_microdollars
        else:
            limit = parse_microdollars(max_cost_usd)
        self._limit = limit
        self._violated = False
        self._held = 0
        self._spent = 0
        self._next_id = 1
        self._entries: dict[int, _Entry] = {}
        self._lock = threading.RLock()

    @property
    def limit_microdollars(self) -> int:
        return self._limit

    @property
    def reserved_microdollars(self) -> int:
        with self._lock:
            return self._held

    @property
    def spent_microdollars(self) -> int:
        with self._lock:
            return self._spent

    @property
    def available_microdollars(self) -> int:
        with self._lock:
            return self._limit - self._held - self._spent

    def reserve(self, amount_usd: object) -> Reservation | None:
        amount = parse_microdollars(amount_usd, allow_zero=False)
        with self._lock:
            if self._violated or self._held + self._spent + amount > self._limit:
                return None
            ticket = Reservation(self._next_id, amount)
            self._next_id += 1
            self._entries[ticket.ticket_id] = _Entry(ticket)
            self._held += amount
            return ticket

    try_reserve = reserve

    def dispatch(self, ticket: Reservation) -> None:
        with self._lock:
            entry = self._entry(ticket)
            if entry.state != "reserved":
                raise ValueError("ticket is not pending dispatch")
            entry.state = "dispatched"

    def cancel(self, ticket: Reservation) -> None:
        with self._lock:
            entry = self._entry(ticket)
            if entry.state != "reserved":
                raise ValueError("ticket cannot be cancelled")
            self._held -= ticket.reserved_microdollars
            entry.state = "cancelled"

    def settle(self, ticket: Reservation, actual_cost_usd: object | None = None) -> int:
        """Close a dispatched ticket and return the charged microdollars."""
        with self._lock:
            entry = self._entry(ticket)
            if entry.state in {"settled", "cancelled"}:
                raise ValueError("ticket already settled")
            if entry.state == "reserved":
                entry.state = "dispatched"
            if actual_cost_usd is None:
                charged = ticket.reserved_microdollars
            else:
                charged = parse_microdollars(actual_cost_usd)
                if charged > ticket.reserved_microdollars:
                    self._violated = True
                    raise SettlementError("actual cost exceeds reservation")
            self._held -= ticket.reserved_microdollars
            self._spent += charged
            entry.state = "settled"
            return charged

    def _entry(self, ticket: Reservation) -> _Entry:
        if not isinstance(ticket, Reservation):
            raise ValueError("unknown ticket")
        entry = self._entries.get(ticket.ticket_id)
        if entry is None or entry.ticket is not ticket:
            raise ValueError("unknown ticket")
        return entry

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "limit_microdollars": self._limit,
                "reserved_microdollars": self._held,
                "spent_microdollars": self._spent,
                "available_microdollars": self._limit - self._held - self._spent,
            }


class MonotonicDeadline:
    """Deadline based on an injectable monotonic clock."""

    def __init__(self, deadline: float, *, clock: Clock = time.monotonic) -> None:
        self._deadline = finite_time(deadline, "deadline")
        self._clock = clock
        self._last_now = float("-inf")
        self._last_now = self._read_clock()

    @classmethod
    def from_timeout_ms(
        cls, timeout_ms: object, *, clock: Clock = time.monotonic
    ) -> MonotonicDeadline:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= 0:
            raise ValueError("invalid deadline")
        now = finite_time(clock())
        duration = finite_time(timeout_ms, "deadline") / 1000.0
        return cls(now + duration, clock=clock)

    after_ms = from_timeout_ms

    @property
    def deadline(self) -> float:
        return self._deadline

    def _read_clock(self) -> float:
        now = finite_time(self._clock())
        self._last_now = max(self._last_now, now)
        return self._last_now

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - self._read_clock())

    def remaining_ms(self) -> int:
        return int(math.ceil(self.remaining_seconds() * 1000.0))

    def expired(self) -> bool:
        return self._read_clock() >= self._deadline

    def ensure_remaining(self) -> None:
        if self.expired():
            raise TimeoutError("deadline exceeded")


Deadline = MonotonicDeadline
