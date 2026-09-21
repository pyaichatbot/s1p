"""R-008: `s1 replay` reports hash reproducibility, never reconstructs input (ADR-019)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from s1_contracts.request import example_request
from s1m.artifacts.bundle import install
from s1router.adapters.audit import FileAuditSink
from s1router.adapters.worker_cli import build_router
from s1router.application.replay import load_record, replay
from s1router.cli import main
from test_local_model import write_bundle

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def installed_model(tmp_path: Path) -> Path:
    root = tmp_path / "installed"
    install(write_bundle(tmp_path / "source"), root)
    return root


def recorded(tmp_path: Path) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    """Run one real decision and return (redacted record, original raw bytes, policy config)."""
    router = build_router(installed_model(tmp_path), None, FileAuditSink(tmp_path / "audit"))
    raw = json.dumps(example_request()).encode()
    router.decide(raw)
    line = (tmp_path / "audit" / "audit.jsonl").read_text().strip().splitlines()[-1]
    return json.loads(line), raw, router.policy.config


@pytest.mark.requirement("R-008")
def test_replay_verifies_matching_input_and_policy() -> None:
    record = {
        "schema_version": "1.0",
        "policy_ref": "a" * 64,
        "task_registry_ref": "b" * 64,
        "input_sha256": __import__("hashlib").sha256(b"payload").hexdigest(),
        "cost_usd": "0.000000",
        "duration_ms": 1.0,
        "outcomes": [],
    }
    report = replay(record, b"payload", None)
    assert report["input"] == "verified"
    assert report["policy"] == "not_supplied"
    assert report["task_registry"] == "not_verifiable"


@pytest.mark.requirement("R-008")
def test_replay_never_claims_reproduction_from_the_hash_alone() -> None:
    """A record never carries raw state; replay must say so, not fabricate a match."""
    record = {
        "schema_version": "1.0",
        "policy_ref": "a" * 64,
        "task_registry_ref": "b" * 64,
        "input_sha256": "0" * 64,
        "cost_usd": "0.000000",
        "duration_ms": 1.0,
        "outcomes": [],
    }
    report = replay(record, b"different bytes entirely", None)
    assert report["input"] == "missing_original_input"
    assert "state" not in report and "raw" not in json.dumps(report)


@pytest.mark.requirement("R-008")
def test_load_record_rejects_a_malformed_record() -> None:
    with pytest.raises(ValueError):
        load_record(b'{"not": "a record"}')
    with pytest.raises(ValueError):
        load_record(b"not json")


@pytest.mark.requirement("R-008")
def test_cli_replay_reports_full_verification_with_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record, raw, config = recorded(tmp_path)
    record_path, state_path, policy_path = (
        tmp_path / "record.json",
        tmp_path / "state.json",
        tmp_path / "policy.json",
    )
    record_path.write_text(json.dumps(record))
    state_path.write_bytes(raw)
    policy_path.write_text(json.dumps(config))

    exit_code = main(
        ["replay", str(record_path), "--state", str(state_path), "--policy", str(policy_path)]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["input"] == "verified"
    assert report["policy"] == "verified"


@pytest.mark.requirement("R-008")
def test_cli_replay_reports_missing_original_input_with_exit_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record, _raw, _config = recorded(tmp_path)
    record_path, state_path = tmp_path / "record.json", tmp_path / "state.json"
    record_path.write_text(json.dumps(record))
    state_path.write_bytes(b"this is not the original request")

    exit_code = main(["replay", str(record_path), "--state", str(state_path)])

    assert exit_code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["input"] == "missing_original_input"
    assert report["policy"] == "not_supplied"


@pytest.mark.requirement("R-008")
def test_cli_replay_reports_policy_mismatch_with_exit_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record, raw, config = recorded(tmp_path)
    record_path, state_path, policy_path = (
        tmp_path / "record.json",
        tmp_path / "state.json",
        tmp_path / "policy.json",
    )
    record_path.write_text(json.dumps(record))
    state_path.write_bytes(raw)
    policy_path.write_text(json.dumps(config | {"deadline_ms": config["deadline_ms"] + 1}))

    exit_code = main(
        ["replay", str(record_path), "--state", str(state_path), "--policy", str(policy_path)]
    )

    assert exit_code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["input"] == "verified"
    assert report["policy"] == "mismatch"


@pytest.mark.requirement("R-008")
def test_cli_replay_rejects_a_malformed_record_with_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record_path, state_path = tmp_path / "record.json", tmp_path / "state.json"
    record_path.write_text('{"not": "a record"}')
    state_path.write_bytes(b"anything")

    exit_code = main(["replay", str(record_path), "--state", str(state_path)])

    assert exit_code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "invalid_request"


@pytest.mark.requirement("R-008")
def test_cli_replay_reports_missing_files_with_exit_four(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "replay",
            str(tmp_path / "absent-record.json"),
            "--state",
            str(tmp_path / "absent-state.json"),
        ]
    )

    assert exit_code == 4
    report = json.loads(capsys.readouterr().out)
    assert report["error"]["code"] == "input_unavailable"


@pytest.mark.requirement("R-008")
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "9.0"),
        ("policy_ref", None),
        ("input_sha256", "not-a-hash"),
        ("cost_usd", 1.0),
        ("duration_ms", float("nan")),
        ("duration_ms", True),
        ("outcomes", "not-a-list"),
        ("secret", "must-not-be-echoed"),
    ],
)
def test_replay_rejects_invalid_typed_record(field: str, value: Any) -> None:
    record = dict(
        schema_version="1.0",
        policy_ref="a" * 64,
        task_registry_ref="b" * 64,
        input_sha256="c" * 64,
        cost_usd="0.000000",
        duration_ms=0,
        outcomes=[dict(index=0, status="review_required", reason="missing_calibration")],
    )
    record[field] = value
    with pytest.raises(ValueError, match="invalid_record"):
        load_record(json.dumps(record).encode())


@pytest.mark.requirement("R-008")
def test_replay_rejects_duplicate_keys_depth_and_oversize() -> None:
    for raw in (
        b'{"schema_version":"1.0","schema_version":"1.0"}',
        b"[" * 2000 + b"]" * 2000,
        b" " * (64 * 1024 + 1),
    ):
        with pytest.raises(ValueError, match="invalid_record"):
            load_record(raw)
