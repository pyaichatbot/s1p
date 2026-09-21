"""Bounded resident worker: length-bounded JSON lines, single-inference concurrency.

Design: docs/s1router/design.md#deployment-resources-and-operations. Scope
decision: docs/decisions.md#adr-017-bounded-resident-worker-as-the-r-009-vertical-slice-2026-09-20.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from s1_contracts.request import ID, _depth_guard

from s1router.domain.admission import TokenBucket

MAX_FRAME_BYTES = 512 * 1024
DEFAULT_CAPACITY = 32
RATE_PER_SECOND = 10.0
BURST = 20
METRIC_LABELS = (
    "accepted",
    "completed",
    "input_too_long",
    "queue_full",
    "rate_limited",
    "invalid_request",
    "cancelled",
    "provider_unavailable",
)


def build_handle(engine: Any) -> Callable[[bytes], dict[str, Any]]:
    """Wrap an application Router so the worker parses identically to the SDK."""
    handle: Callable[[bytes], dict[str, Any]] = engine.decide
    return handle


def _peek_request_id(raw: bytes) -> str | None:
    try:
        bounded = raw[:MAX_FRAME_BYTES]
        _depth_guard(bounded)
        value = json.loads(bounded)
    except ValueError:
        return None
    request_id = value.get("request_id") if isinstance(value, dict) else None
    return request_id if isinstance(request_id, str) and ID.fullmatch(request_id) else None


class WorkerService:
    """Admission queue and single-worker loop over an injected decision handler.

    Frame admission (``submit``) and processing (``run_once``) are separated
    and thread-free to call directly, so behavioral tests can force exact
    queue-full and shutdown interleavings the same way R-006/R-011 concurrency
    tests do, without depending on real process stdio. The stdio-facing `s1
    worker` command wires reader/writer threads over this core.
    """

    def __init__(
        self,
        handle: Callable[[bytes], dict[str, Any]],
        *,
        smoke_test: Callable[[], Any],
        write: Callable[[dict[str, Any]], None],
        log: Callable[[str], None],
        capacity: int = DEFAULT_CAPACITY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("invalid_configuration")
        self._handle = handle
        self._smoke_test = smoke_test
        self._write = write
        self._log = log
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=capacity)
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._bucket = TokenBucket(RATE_PER_SECOND, BURST, clock)
        self._counts = dict.fromkeys(METRIC_LABELS, 0)
        self._ready = False
        self._stopping = False

    def ready(self) -> bool:
        with self._state_lock:
            return self._ready and not self._stopping

    def metrics(self) -> dict[str, int]:
        """Return fixed-label counters without request IDs or user data."""
        with self._state_lock:
            return dict(self._counts)

    def start(self) -> None:
        """Verify the pinned artifact via a fixture smoke test, then publish readiness.

        Readiness is never published if the smoke test raises: the caller must
        not accept traffic against an unverified or corrupt artifact.
        """
        with self._state_lock:
            if self._stopping:
                raise ValueError("cancelled")
        result = self._smoke_test()
        if not _valid_smoke(result):
            raise ValueError("worker_smoke_test_failed")
        with self._state_lock:
            if self._stopping:
                raise ValueError("cancelled")
            self._ready = True
        self._emit({"schema_version": "1.0", "event": "ready"})

    def submit(self, raw: bytes) -> bool:
        """Admit one bounded frame; return False on overflow or oversize.

        An oversized frame or a full queue is rejected immediately with a
        typed retryable error addressed to the frame's own request_id (when
        parseable), never silently dropped and never blocking the caller.
        """
        with self._state_lock:
            if not self._ready or self._stopping:
                reason = "cancelled"
            elif len(raw) > MAX_FRAME_BYTES:
                reason = "input_too_long"
            elif self._queue.full():
                reason = "queue_full"
            elif not self._bucket.allow():
                reason = "rate_limited"
            else:
                try:
                    self._queue.put_nowait(raw)
                except queue.Full:
                    reason = "queue_full"
                else:
                    self._counts["accepted"] += 1
                    return True
        self._reject(raw, reason)
        return False

    def shutdown(self) -> None:
        """Signal the worker loop to stop once pending frames are drained."""
        with self._state_lock:
            self._stopping = True

    def run_once(self) -> bool:
        """Process one queued frame, or the shutdown sentinel.

        Returns False once shutdown is reached, so a caller can loop
        ``while worker.run_once(): ...`` for single-inference concurrency.
        """
        while True:
            try:
                raw = self._queue.get(timeout=0.1)
                break
            except queue.Empty:
                with self._state_lock:
                    if self._stopping:
                        return False
        if raw is None:
            return False
        try:
            result = self._handle(raw)
        except ValueError as exc:
            code = "invalid_request" if str(exc) == "invalid_request" else "provider_unavailable"
            self._log(f"frame_error:{type(exc).__name__}")
            self._reject(raw, code)
            return True
        except Exception as exc:  # noqa: BLE001 - isolate one frame, never crash the worker
            self._log(f"frame_error:{type(exc).__name__}")
            self._reject(raw, "provider_unavailable")
            return True
        self._emit(result)
        self._count("completed")
        return True

    def _reject(self, raw: bytes, code: str) -> None:
        self._count(code)
        self._emit(
            {
                "schema_version": "1.0",
                "request_id": _peek_request_id(raw),
                "error": {
                    "code": code,
                    "message": code.replace("_", " "),
                    "retryable": code not in {"cancelled", "invalid_request"},
                },
            }
        )

    def _count(self, label: str) -> None:
        with self._state_lock:
            if label in self._counts:
                self._counts[label] += 1

    def _emit(self, value: dict[str, Any]) -> None:
        with self._write_lock:
            self._write(value)


def _valid_smoke(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        return False
    if not isinstance(value.get("audit_ref"), str) or not value["audit_ref"]:
        return False
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        return False
    prediction = outcomes[0].get("prediction") if isinstance(outcomes[0], dict) else None
    if not isinstance(prediction, dict) or prediction.get("status") != "predicted":
        return False
    return bool(prediction.get("selected_id")) and isinstance(prediction.get("probabilities"), list)
