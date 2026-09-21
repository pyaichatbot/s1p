"""``s1 worker``: stdio wiring over the bounded WorkerService core.

Design: docs/s1router/design.md#deployment-resources-and-operations. Scope
decision: docs/decisions.md#adr-017. This module is the thin adapter ADR-017
describes: it composes a real ``Router`` (policy + one local provider + its
declared tasks + a file-backed audit sink), then drives ``WorkerService``
over real process stdio. The injectable core (frame admission, single
inference concurrency, queue-full/shutdown semantics) lives in ``worker.py``
and is exercised directly by behavioral tests without process stdio.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from s1_contracts.prediction import validate_prediction
from s1_contracts.request import example_request, parse_request

from s1router.adapters.audit import FileAuditSink
from s1router.adapters.local import LocalProvider
from s1router.adapters.worker import WorkerService, build_handle
from s1router.adapters.worker_stream import frames
from s1router.application.engine import Router
from s1router.domain.policy import PolicySnapshot, default_policy


def build_router(model_path: Path, policy_path: Path | None, audit: Any) -> Router:
    """Compose one local provider's declared tasks under its own policy profile.

    A worker serves exactly the provider it was installed with, so the
    policy's provider list is fixed to that provider's id rather than left
    for an operator to mismatch; ``policy_path`` overrides everything else
    (deadlines, remote/data-policy flags, rules).
    """
    provider = LocalProvider(model_path)
    if provider.capabilities is None:
        raise ValueError("artifact_corrupt")
    config = json.loads(policy_path.read_text()) if policy_path else default_policy()
    config = config | {"providers": [provider.provider_id]}
    policy = PolicySnapshot.from_dict(config)
    return Router(policy, (provider,), provider.capabilities.tasks, audit)


def smoke_test(router: Router) -> dict[str, Any]:
    """Exercise the full decision path once before publishing readiness.

    Manifest/hash verification already happened inside ``LocalProvider``'s
    constructor (raised there, never reaching this point). This additionally
    proves the composed pipeline itself works end to end: policy resolves,
    the provider process starts and replies, and the audit sink is writable.
    """
    raw = json.dumps(example_request()).encode()
    request = parse_request(raw)
    result = router.decide(raw)
    if result["schema_version"] != "1.0" or not result["audit_ref"]:
        raise ValueError("worker_smoke_test_failed")
    outcome = result["outcomes"][0]
    prediction = validate_prediction(outcome["prediction"], request["questions"][0])
    if prediction["status"] != "predicted" or not outcome["attempts"]:
        raise ValueError("worker_smoke_test_failed")
    if outcome["attempts"][0].get("provider_id") != "s1m-sparse":
        raise ValueError("worker_smoke_test_failed")
    return result


def run(
    model_path: Path,
    policy_path: Path | None,
    audit_dir: Path,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    def log(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    def write(value: dict[str, Any]) -> None:
        print(json.dumps(value, allow_nan=False), flush=True)

    try:
        router = build_router(model_path, policy_path, FileAuditSink(audit_dir))
    except (ValueError, OSError) as exc:
        log(f"worker_start_failed:{type(exc).__name__}")
        return 4
    worker = WorkerService(
        build_handle(router),
        smoke_test=lambda: smoke_test(router),
        write=write,
        log=log,
        clock=clock,
    )
    try:
        worker.start()
    except (ValueError, OSError, TimeoutError) as exc:
        log(f"worker_start_failed:{type(exc).__name__}")
        return 4
    stopping = threading.Event()

    def stop(*_: Any) -> None:
        stopping.set()
        worker.shutdown()

    signal.signal(signal.SIGTERM, stop)
    processor = threading.Thread(target=lambda: _drain(worker), daemon=True)
    processor.start()
    for frame in frames(sys.stdin.buffer, 512 * 1024, stopping):
        if stopping.is_set():
            break
        worker.submit(frame)
    worker.shutdown()
    processor.join()
    log("worker_stopped")
    return 0


def _drain(worker: WorkerService) -> None:
    while worker.run_once():
        pass
