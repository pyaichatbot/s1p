"""JSON CLI adapter for the L1 local-only runtime."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from s1_contracts.request import MAX_BYTES, example_request, parse_request
from s1m.artifacts.bundle import install

from s1router.adapters import worker_cli
from s1router.application.replay import load_record, replay
from s1router.domain.policy import PolicySnapshot
from s1router.domain.rules import decide
from s1router.telemetry import EventStore


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, allow_nan=False))


def _error(code: str) -> None:
    _emit(
        {
            "schema_version": "1.0",
            "request_id": None,
            "error": {
                "code": code,
                "message": code.replace("_", " "),
                "retryable": code != "invalid_request",
            },
        }
    )


def _policy_validate(path: Path) -> int:
    """Thin wrapper over PolicySnapshot.from_dict (R-002); no new decision logic."""
    try:
        raw = path.read_bytes()
    except OSError:
        _error("input_unavailable")
        return 4
    try:
        policy = PolicySnapshot.from_dict(json.loads(raw))
    except (ValueError, TypeError):
        _error("invalid_configuration")
        return 2
    _emit({"schema_version": "1.0", "valid": True, "policy_ref": policy.reference})
    return 0


def _model_install(source: Path, root: Path) -> int:
    """Thin wrapper over s1m.artifacts.bundle.install (R-010); no new atomicity logic."""
    try:
        reference = install(source, root)
    except ValueError:
        _error("artifact_corrupt")
        return 2
    except OSError:
        _error("input_unavailable")
        return 4
    _emit({"schema_version": "1.0", "installed": True, "model_ref": reference, "root": str(root)})
    return 0


def _replay(record_path: Path, state_path: Path, policy_path: Path | None) -> int:
    """Report hash reproducibility for one redacted record (R-008); never reconstructs input."""
    try:
        record_raw = record_path.read_bytes()
        state = state_path.read_bytes()
        policy_raw = policy_path.read_bytes() if policy_path else None
    except OSError:
        _error("input_unavailable")
        return 4
    try:
        record = load_record(record_raw)
        policy_config = json.loads(policy_raw) if policy_raw is not None else None
    except ValueError:
        _error("invalid_request")
        return 2
    report = replay(record, state, policy_config)
    _emit(report)
    return 0 if report["input"] == "verified" and report["policy"] != "mismatch" else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="s1", description="Local rules and explicit abstention")
    commands = parser.add_subparsers(dest="command", required=True)
    request_cmd = commands.add_parser("decide")
    request_cmd.add_argument("file")
    request_cmd.add_argument("--json", action="store_true")
    commands.add_parser("example")
    commands.add_parser("doctor")
    observation = commands.add_parser("observe")
    observation.add_argument("--record-incident", action="store_true")
    worker = commands.add_parser("worker")
    worker.add_argument("--model", required=True)
    worker.add_argument("--policy")
    policy_group = commands.add_parser("policy").add_subparsers(
        dest="policy_command", required=True
    )
    policy_group.add_parser("validate").add_argument("file")
    model_group = commands.add_parser("model").add_subparsers(dest="model_command", required=True)
    model_install_cmd = model_group.add_parser("install")
    model_install_cmd.add_argument("source")
    model_install_cmd.add_argument("--root")
    replay_cmd = commands.add_parser("replay")
    replay_cmd.add_argument("record")
    replay_cmd.add_argument("--state", required=True)
    replay_cmd.add_argument("--policy")
    args = parser.parse_args(argv)
    if args.command == "example":
        _emit(example_request())
        return 0
    if args.command == "worker":
        return worker_cli.run(
            Path(args.model),
            Path(args.policy) if args.policy else None,
            Path(os.environ.get("S1_HOME", ".local/s1/state")) / "worker-audit",
        )
    if args.command == "policy":
        return _policy_validate(Path(args.file))
    if args.command == "model":
        root = (
            Path(args.root)
            if args.root
            else Path(os.environ.get("S1_HOME", ".local/s1/state")) / "models"
        )
        return _model_install(Path(args.source), root)
    if args.command == "replay":
        return _replay(
            Path(args.record), Path(args.state), Path(args.policy) if args.policy else None
        )
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", os.environ.get("S1_RELEASE_ID", "development")):
        _error("invalid_configuration")
        return 4
    try:
        store = EventStore(Path(os.environ.get("S1_HOME", ".local/s1/state")))
        if args.command == "doctor":
            store.health()
            _emit({"status": "ready", "layer": 1, "model_loaded": False, "remote_enabled": False})
            return 0
        if args.command == "observe":
            report = store.observe()
            if args.record_incident:
                path = store.record_incident(report, os.environ.get("S1_RELEASE_ID", "development"))
                report["incident"] = str(path) if path else None
            _emit(report)
            return 3 if report["findings"] else 0
    except OSError:
        _error("audit_unavailable")
        return 4
    try:
        if args.file == "-":
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with Path(args.file).open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
    except OSError:
        _error("input_unavailable")
        return 4
    start = time.monotonic()
    try:
        request = parse_request(raw)
    except ValueError:
        duration = (time.monotonic() - start) * 1000
        try:
            store.append(
                "invalid_request",
                "invalid_request",
                duration,
                os.environ.get("S1_RELEASE_ID", "development"),
            )
        except OSError:
            _error("audit_unavailable")
            return 4
        _error("invalid_request")
        return 2
    result = decide(request)
    duration = (time.monotonic() - start) * 1000
    result["timings_ms"]["processing"] = duration
    review = any(outcome["status"] == "review_required" for outcome in result["outcomes"])
    status = "review_required" if review else "answered_rule"
    reason = next((outcome["reason"] for outcome in result["outcomes"] if outcome["reason"]), None)
    try:
        store.append(status, reason, duration, os.environ.get("S1_RELEASE_ID", "development"))
    except OSError:
        _error("audit_unavailable")
        return 4
    result["audit_ref"] = "local-events"
    _emit(result)
    return 3 if review else 0
