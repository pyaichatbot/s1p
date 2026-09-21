"""R-009: `s1 worker` composes a real Router and drives it over real stdio."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from s1_contracts.request import example_request
from s1m.artifacts.bundle import install
from s1router.adapters import worker_cli
from s1router.adapters.audit import FileAuditSink
from s1router.application.engine import Router
from test_local_model import write_bundle

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def installed_model(tmp_path: Path) -> Path:
    root = tmp_path / "installed"
    install(write_bundle(tmp_path / "source"), root)
    return root


def worker_process(model_path: Path, audit_path: Path) -> subprocess.Popen[bytes]:
    package_paths = ["packages/contracts/src", "packages/router/src", "packages/model/src"]
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join(str(Path.cwd() / path) for path in package_paths)
    }
    return subprocess.Popen(
        [sys.executable, "-m", "s1router", "worker", "--model", str(model_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )


@pytest.mark.requirement("R-009")
def test_build_router_composes_real_provider_under_its_own_policy_profile(tmp_path: Path) -> None:
    router = worker_cli.build_router(
        installed_model(tmp_path), None, FileAuditSink(tmp_path / "audit")
    )
    assert isinstance(router, Router)
    assert router.policy.config["providers"] == ["s1m-sparse"]
    result = router.decide(json.dumps(example_request()).encode())
    assert result["schema_version"] == "1.0"
    assert result["audit_ref"] is not None


@pytest.mark.requirement("R-009")
def test_smoke_test_passes_for_a_real_installed_bundle(tmp_path: Path) -> None:
    router = worker_cli.build_router(
        installed_model(tmp_path), None, FileAuditSink(tmp_path / "audit")
    )
    worker_cli.smoke_test(router)  # must not raise


@pytest.mark.requirement("R-009")
def test_worker_cli_parses_identically_to_sdk_and_separates_stdout_from_stderr(
    tmp_path: Path, monkeypatch: Any
) -> None:
    model_path = installed_model(tmp_path)
    router = worker_cli.build_router(model_path, None, FileAuditSink(tmp_path / "audit"))
    direct = router.decide(json.dumps(example_request()).encode())

    request_frame = json.dumps(example_request()).encode() + b"\n"
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(request_frame)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    exit_code = worker_cli.run(model_path, None, tmp_path / "worker-audit")

    assert exit_code == 0
    lines = [json.loads(line) for line in out.getvalue().splitlines() if line]
    assert lines[0] == {"schema_version": "1.0", "event": "ready"}
    reply = lines[1]
    for result in (direct, reply):
        result.pop("timings_ms")
        result.pop("audit_ref")
        for outcome in result["outcomes"]:
            for attempt in outcome["attempts"]:
                attempt.pop("elapsed_ms")  # wall-clock, not part of the parity claim
    assert direct == reply
    assert "outcomes" not in err.getvalue()
    assert "worker_stopped" in err.getvalue()


@pytest.mark.requirement("R-009")
def test_worker_cli_rejects_oversized_frame_without_crashing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from s1router.adapters.worker import MAX_FRAME_BYTES

    huge = json.dumps({"request_id": "big"}).encode() + b" " * MAX_FRAME_BYTES + b"\n"
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(huge)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    exit_code = worker_cli.run(installed_model(tmp_path), None, tmp_path / "worker-audit")

    assert exit_code == 0
    lines = [json.loads(line) for line in out.getvalue().splitlines() if line]
    assert lines[-1]["error"]["code"] == "input_too_long"


@pytest.mark.requirement("R-009")
def test_worker_cli_reports_start_failure_without_crashing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"")))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)

    exit_code = worker_cli.run(tmp_path / "missing-model", None, tmp_path / "worker-audit")

    assert exit_code == 4
    assert "worker_start_failed" in err.getvalue()


@pytest.mark.requirement("R-009")
def test_worker_cli_stops_reading_promptly_once_signalled(tmp_path: Path, monkeypatch: Any) -> None:
    """A SIGTERM sets the stop flag the read loop checks; no further frame is admitted."""
    model_path = installed_model(tmp_path)
    frames = (json.dumps(example_request()).encode() + b"\n") * 3
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(frames)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    real_signal = signal.signal

    def fire_immediately(sig: int, handler: Any) -> Any:
        registered = real_signal(sig, handler)
        if callable(handler) and handler.__name__ == "stop":
            handler(sig, None)
        return registered

    monkeypatch.setattr(signal, "signal", fire_immediately)

    exit_code = worker_cli.run(model_path, None, tmp_path / "worker-audit")

    assert exit_code == 0
    lines = [json.loads(line) for line in out.getvalue().splitlines() if line]
    assert lines == [{"schema_version": "1.0", "event": "ready"}]
    assert "worker_stopped" in err.getvalue()


@pytest.mark.requirement("R-009")
def test_worker_process_terminates_on_sigterm_while_stdin_is_idle(tmp_path: Path) -> None:
    process = worker_process(installed_model(tmp_path), tmp_path / "worker-audit")
    assert process.stdout is not None
    assert json.loads(process.stdout.readline()) == {"schema_version": "1.0", "event": "ready"}
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=3) == 0
    assert process.stdin is not None
    process.stdin.close()
    process.stdout.close()
    assert process.stderr is not None
    process.stderr.close()


@pytest.mark.requirement("R-009")
def test_worker_process_bounds_unterminated_oversized_frame(tmp_path: Path) -> None:
    from s1router.adapters.worker import MAX_FRAME_BYTES

    process = worker_process(installed_model(tmp_path), tmp_path / "worker-audit")
    assert process.stdin is not None and process.stdout is not None
    assert json.loads(process.stdout.readline())["event"] == "ready"
    process.stdin.write(json.dumps({"request_id": "huge"}).encode() + b" " * MAX_FRAME_BYTES)
    process.stdin.flush()
    response = json.loads(process.stdout.readline())
    assert response["error"]["code"] == "input_too_long"
    process.stdin.close()
    assert process.wait(timeout=3) == 0
    process.stdout.close()
    assert process.stderr is not None
    process.stderr.close()
