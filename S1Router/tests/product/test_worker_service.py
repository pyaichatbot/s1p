"""R-009: bounded resident worker frame admission, readiness and isolation."""

from __future__ import annotations

import json
import threading
from typing import Any

import pytest
from s1_contracts.request import example_request, task_definition
from s1router.adapters.worker import MAX_FRAME_BYTES, WorkerService, build_handle
from s1router.application.engine import Router
from s1router.domain.acceptance import CalibrationProfile
from s1router.domain.capabilities import Capabilities, RegisteredTask
from s1router.domain.policy import PolicySnapshot, default_policy
from s1router.ports.providers import ProviderReply

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


class Audit:
    def append(self, record: dict[str, Any]) -> str:
        return "record-1"


class Stub:
    provider_id = "local"
    remote = False
    endpoint: str | None = None
    max_cost_usd = "0.000000"
    capabilities: Capabilities | None = None
    calibration: CalibrationProfile | None = None

    def count_tokens(self, text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        raise AssertionError("must not be called: no rule/task match is expected in this fixture")


def router() -> Router:
    policy = PolicySnapshot.from_dict(default_policy())
    return Router(policy, (Stub(),), (RegisteredTask.create(task_definition()),), Audit())


def service(
    handle: Any, *, capacity: int = 32, clock: Any = None, smoke: Any = None
) -> tuple[WorkerService, list[dict[str, Any]], list[str]]:
    written: list[dict[str, Any]] = []
    logged: list[str] = []
    options: dict[str, Any] = dict(
        smoke_test=smoke
        or (
            lambda: {
                "schema_version": "1.0",
                "audit_ref": "smoke",
                "outcomes": [
                    {
                        "prediction": {
                            "status": "predicted",
                            "selected_id": "bug",
                            "probabilities": [],
                        }
                    }
                ],
            }
        ),
        write=written.append,
        log=logged.append,
        capacity=capacity,
    )
    if clock is not None:
        options["clock"] = clock
    worker = WorkerService(handle, **options)
    return worker, written, logged


def _raise() -> None:
    raise ValueError("artifact_corrupt")


def frame(request_id: str) -> bytes:
    return json.dumps({"request_id": request_id}).encode()


@pytest.mark.requirement("R-009")
def test_readiness_only_after_smoke_test_succeeds() -> None:
    written: list[dict[str, Any]] = []
    failing = WorkerService(
        lambda raw: {}, smoke_test=_raise, write=written.append, log=lambda _: None
    )
    with pytest.raises(ValueError):
        failing.start()
    assert not failing.ready()
    assert written == []
    worker, written2, _ = service(lambda raw: {})
    worker.start()
    assert worker.ready()
    assert written2 == [{"schema_version": "1.0", "event": "ready"}]


@pytest.mark.requirement("R-009")
def test_readiness_rejects_schema_only_smoke_result() -> None:
    worker, written, _ = service(lambda raw: {}, smoke=lambda: {"schema_version": "1.0"})
    with pytest.raises(ValueError, match="worker_smoke_test_failed"):
        worker.start()
    assert not worker.ready()
    assert written == []


@pytest.mark.requirement("R-009")
def test_submit_is_rejected_before_ready_and_after_shutdown_atomically() -> None:
    worker, written, _ = service(lambda raw: {"schema_version": "1.0"})
    assert worker.submit(frame("early")) is False
    assert written[-1]["error"]["code"] == "worker_not_ready"
    worker.start()
    assert worker.submit(frame("accepted")) is True
    worker.shutdown()
    assert worker.submit(frame("late")) is False
    assert written[-1]["error"]["code"] == "cancelled"
    assert worker.run_once() is True
    assert worker.run_once() is False


@pytest.mark.requirement("R-011")
def test_worker_rate_limit_persists_for_service_lifetime_with_fake_clock() -> None:
    now = [100.0]
    worker, written, _ = service(lambda raw: {"schema_version": "1.0"}, clock=lambda: now[0])
    worker.start()
    assert all(worker.submit(frame(str(index))) for index in range(20))
    assert worker.submit(frame("limited")) is False
    assert written[-1]["error"]["code"] == "rate_limited"
    now[0] += 0.1
    assert worker.submit(frame("refilled")) is True
    metrics = worker.metrics()
    assert metrics["accepted"] == 21
    assert metrics["rate_limited"] == 1
    assert set(metrics) == {
        "accepted",
        "completed",
        "input_too_long",
        "queue_full",
        "rate_limited",
        "invalid_request",
        "worker_not_ready",
        "cancelled",
        "provider_unavailable",
    }


@pytest.mark.requirement("R-009")
def test_oversized_frame_rejected_without_reaching_handler() -> None:
    calls: list[bytes] = []

    def handle(raw: bytes) -> dict[str, Any]:
        calls.append(raw)
        return {"ok": True}

    worker, written, _ = service(handle)
    worker.start()
    huge = json.dumps({"request_id": "big"}).encode() + b" " * MAX_FRAME_BYTES
    assert worker.submit(huge) is False
    assert calls == []
    assert written[-1:] == [
        {
            "schema_version": "1.0",
            "request_id": "big",
            "error": {"code": "input_too_long", "message": "input too long", "retryable": True},
        }
    ]


@pytest.mark.requirement("R-009")
def test_queue_full_is_deterministic_and_never_duplicates_work() -> None:
    started, release = threading.Event(), threading.Event()
    calls: list[str] = []

    def handle(raw: bytes) -> dict[str, Any]:
        request_id = json.loads(raw)["request_id"]
        calls.append(request_id)
        if request_id == "a":
            started.set()
            assert release.wait(timeout=2)
        return {"schema_version": "1.0", "request_id": request_id}

    worker, written, _ = service(handle, capacity=2)
    worker.start()
    assert worker.submit(frame("a")) is True
    processor = threading.Thread(target=worker.run_once)
    processor.start()
    assert started.wait(timeout=2)  # "a" is dequeued and now blocking inside handle()
    assert worker.submit(frame("b")) is True
    assert worker.submit(frame("c")) is True
    assert worker.submit(frame("d")) is False  # queue already holds b, c: capacity 2
    release.set()
    processor.join(timeout=2)
    assert calls == ["a"]
    assert [w["error"]["code"] for w in written if "error" in w] == ["queue_full"]
    assert worker.run_once() is True
    assert worker.run_once() is True
    assert calls == ["a", "b", "c"]


@pytest.mark.requirement("R-009")
def test_shutdown_drains_pending_frames_then_stops() -> None:
    processed: list[str] = []

    def handle(raw: bytes) -> dict[str, Any]:
        processed.append(json.loads(raw)["request_id"])
        return {"schema_version": "1.0"}

    worker, _, _ = service(handle)
    worker.start()
    assert worker.submit(frame("x")) is True
    worker.shutdown()
    assert worker.run_once() is True
    assert processed == ["x"]
    assert worker.run_once() is False


@pytest.mark.requirement("R-009")
def test_handler_failure_is_isolated_and_never_logs_raw_state() -> None:
    def handle(raw: bytes) -> dict[str, Any]:
        raise ValueError("secret provider diagnostics for " + raw.decode())

    worker, written, logged = service(handle)
    worker.start()
    worker.submit(json.dumps({"request_id": "z", "state": "private"}).encode())
    worker.run_once()
    assert written[-1]["error"]["code"] == "provider_unavailable"
    assert "secret" not in json.dumps(written)
    assert "private" not in json.dumps(logged)
    assert logged == ["frame_error:ValueError"]


@pytest.mark.requirement("R-009")
def test_malformed_request_is_a_typed_invalid_request() -> None:
    def handle(raw: bytes) -> dict[str, Any]:
        raise ValueError("invalid_request")

    worker, written, _ = service(handle)
    worker.start()
    assert worker.submit(b"not-json") is True
    assert worker.run_once() is True
    assert written[-1]["error"] == {
        "code": "invalid_request",
        "message": "invalid request",
        "retryable": False,
    }


@pytest.mark.requirement("R-009")
def test_default_handle_delegates_identically_to_sdk() -> None:
    engine = router()
    handle = build_handle(engine)
    raw = json.dumps(example_request()).encode()
    direct, via_handle = engine.decide(raw), handle(raw)
    for result in (direct, via_handle):
        result.pop("timings_ms")  # wall-clock, not part of the parity claim
    assert direct == via_handle
    with pytest.raises(ValueError):
        handle(b"not json")
    with pytest.raises(ValueError):
        engine.decide(b"not json")
