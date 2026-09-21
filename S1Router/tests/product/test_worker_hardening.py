"""Existing worker rejection and shutdown safety (R-009/R-011)."""

import json
import threading
from typing import Any

import pytest
from test_worker_service import service

pytestmark = [pytest.mark.behavioral, pytest.mark.requirement("R-009")]


@pytest.mark.parametrize(
    "raw",
    [b"[" * 2000, json.dumps({"request_id": "x" * 129}).encode(), b'{"request_id":"bad id"}'],
    ids=["deep", "long-id", "invalid-id"],
)
def test_rejection_never_crashes_or_echoes_invalid_identifiers(raw: bytes) -> None:
    worker, written, _ = service(lambda raw: {})
    assert worker.submit(raw) is False
    assert written[-1]["request_id"] is None
    assert written[-1]["error"]["code"] == "cancelled"


def test_rejection_callback_can_read_worker_metrics() -> None:
    worker, _, _ = service(lambda raw: {})
    observed: list[Any] = []
    worker._write = lambda value: observed.append(worker.metrics())
    thread = threading.Thread(target=lambda: worker.submit(b"{}"), daemon=True)
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive(), "rejection callback deadlocked on admission lock"
    assert observed[0]["cancelled"] == 1


@pytest.mark.parametrize("fail_read", [False, True])
def test_stdio_restores_signal_handler_and_shuts_down_on_read_failure(
    monkeypatch: Any, tmp_path: Any, fail_read: bool
) -> None:
    import signal

    from s1router.adapters import worker_cli

    worker, _, _ = service(lambda raw: {})
    monkeypatch.setattr(worker_cli, "build_router", lambda *args: None)
    monkeypatch.setattr(worker_cli, "WorkerService", lambda *args, **kwargs: worker)
    # build_handle reads .decide; the fake service ignores the handle.
    monkeypatch.setattr(worker_cli, "build_handle", lambda engine: lambda raw: {})
    original = signal.getsignal(signal.SIGTERM)

    def read_frames(*args: Any) -> Any:
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        # Simulate SIGTERM interrupting admission while its state lock is held.
        with worker._state_lock:
            # Intercept shutdown to detect unsafe lock acquisition without hanging pytest.
            real_shutdown = worker.shutdown
            monkeypatch.setattr(
                worker,
                "shutdown",
                lambda: pytest.fail("signal handler called lock-taking shutdown"),
            )
            try:
                handler(signal.SIGTERM, None)
            finally:
                monkeypatch.setattr(worker, "shutdown", real_shutdown)
        if fail_read:
            raise OSError("input disconnected")
        return iter(())

    monkeypatch.setattr(worker_cli, "frames", read_frames)
    try:
        if fail_read:
            with pytest.raises(OSError, match="input disconnected"):
                worker_cli.run(tmp_path, None, tmp_path)
        else:
            assert worker_cli.run(tmp_path, None, tmp_path) == 0
        assert not worker.ready()
        assert signal.getsignal(signal.SIGTERM) == original
    finally:
        worker.shutdown()
        signal.signal(signal.SIGTERM, original)


def test_sigterm_handler_is_installed_before_readiness_is_published(
    monkeypatch: Any, tmp_path: Any
) -> None:
    import signal

    from s1router.adapters import worker_cli

    original = signal.getsignal(signal.SIGTERM)
    worker, _, _ = service(lambda raw: {})
    real_start = worker.start

    def checked_start() -> None:
        assert signal.getsignal(signal.SIGTERM) != original
        real_start()

    monkeypatch.setattr(worker, "start", checked_start)
    monkeypatch.setattr(worker_cli, "WorkerService", lambda *args, **kwargs: worker)
    monkeypatch.setattr(worker_cli, "build_router", lambda *args: None)
    monkeypatch.setattr(worker_cli, "build_handle", lambda engine: lambda raw: {})
    monkeypatch.setattr(worker_cli, "frames", lambda *args: iter(()))
    assert worker_cli.run(tmp_path, None, tmp_path) == 0
    assert signal.getsignal(signal.SIGTERM) == original
