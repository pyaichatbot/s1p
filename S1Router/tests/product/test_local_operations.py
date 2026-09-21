"""L1 real-filesystem observation and command acceptance."""

from __future__ import annotations

import importlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


def api(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        pytest.fail(f"Missing L1 implementation: {name}")


@pytest.mark.requirement("L1-004")
def test_private_bounded_events_and_minimum_sample_alerts(tmp_path: Path) -> None:
    telemetry = api("s1router.telemetry")
    store = telemetry.EventStore(tmp_path, max_bytes=1024)
    for _ in range(40):
        store.append("answered_rule", None, 1.0, "release-a")
    assert len(list(tmp_path.glob("events*.jsonl"))) <= 2
    assert all(p.stat().st_size <= 1024 for p in tmp_path.glob("events*.jsonl"))
    assert (tmp_path.stat().st_mode & 0o777) == 0o700
    assert all((p.stat().st_mode & 0o777) == 0o600 for p in tmp_path.glob("events*.jsonl"))
    report = store.observe()
    assert report["sample_count"] > 0
    assert "request_id" not in "".join(p.read_text() for p in tmp_path.glob("events*.jsonl"))
    large = telemetry.EventStore(tmp_path / "large")
    for _ in range(19):
        large.append("error", "internal_error", 15.0, "release-a")
    assert large.observe()["findings"] == []
    large.append("error", "internal_error", 15.0, "release-a")
    assert set(large.observe()["findings"]) == {"processing_errors", "processing_latency"}
    for _ in range(20):
        large.append("invalid_request", "invalid_request", 0.1, "release-a")
    assert "invalid_requests" in large.observe()["findings"]


@pytest.mark.requirement("L1-004")
def test_corrupt_telemetry_is_actionable_and_incidents_are_deduplicated(tmp_path: Path) -> None:
    telemetry = api("s1router.telemetry")
    store = telemetry.EventStore(tmp_path)
    store.append("answered_rule", None, 1.0, "release-a")
    with (tmp_path / "events.jsonl").open("a") as stream:
        stream.write('{"raw-secret": "must never appear in incident"}\n')
    report = store.observe()
    assert report["corrupt_records"] == 1
    assert "telemetry_corrupt" in report["findings"]
    first = store.record_incident(report, "release-a")
    second = store.record_incident(report, "release-a")
    assert first == second
    assert len(list((tmp_path / "incidents").glob("*.md"))) == 1
    assert "raw-secret" not in first.read_text()
    assert "must never appear" not in first.read_text()


@pytest.mark.requirement("L1-004")
def test_retention_invalid_events_and_empty_observation(tmp_path: Path) -> None:
    telemetry = api("s1router.telemetry")
    store = telemetry.EventStore(tmp_path)
    assert store.observe()["status"] == "insufficient_data"
    for args in [
        ("wrong", None, 1, "r"),
        ("error", "raw payload", 1, "r"),
        ("error", None, float("nan"), "r"),
        ("error", None, -1, "r"),
        ("error", None, 1, "../raw"),
    ]:
        with pytest.raises(ValueError):
            store.append(*args)
    old = {
        "timestamp": time.time() - 8 * 86400,
        "release_id": "old",
        "status": "answered_rule",
        "reason": None,
        "duration_ms": 1.0,
    }
    (tmp_path / "events.jsonl").write_text(json.dumps(old) + "\n")
    assert store.observe()["sample_count"] == 0
    assert "old" not in (tmp_path / "events.jsonl").read_text()
    (tmp_path / "events.jsonl").write_text("x" * (1024 * 1024 + 1))
    assert "telemetry_corrupt" in store.observe()["findings"]


@pytest.mark.requirement("L1-005")
def test_cli_json_exit_codes_and_redaction(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = api("s1router.cli")
    contract = api("s1_contracts.request")
    monkeypatch.setenv("S1_HOME", str(tmp_path / "state"))
    assert cli.main(["example"]) == 0
    request = json.loads(capsys.readouterr().out)
    assert request == contract.example_request()
    path = tmp_path / "request.json"
    request["state"]["declared_change_type"] = "bug"
    request["state"]["body"] = "secret never log this"
    path.write_text(json.dumps(request))
    assert cli.main(["decide", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["outcomes"][0]["selected_id"] == "bug"
    del request["state"]["declared_change_type"]
    path.write_text(json.dumps(request))
    assert cli.main(["decide", str(path)]) == 3
    assert json.loads(capsys.readouterr().out)["outcomes"][0]["status"] == "review_required"
    path.write_text('{"secret": "secret never log this"}')
    assert cli.main(["decide", str(path)]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["error"]["code"] == "invalid_request"
    assert "secret never" not in output.out + output.err
    assert cli.main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"
    assert cli.main(["observe", "--record-incident"]) == 0
    assert json.loads(capsys.readouterr().out)["sample_count"] == 3
    assert "secret never" not in "".join(
        p.read_text() for p in (tmp_path / "state").glob("*.jsonl")
    )


@pytest.mark.requirement("L1-005")
def test_cli_io_failure_cannot_return_an_answer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = api("s1router.cli")
    contract = api("s1_contracts.request")
    bad_home = tmp_path / "not-a-directory"
    bad_home.write_text("occupied")
    monkeypatch.setenv("S1_HOME", str(bad_home))
    path = tmp_path / "request.json"
    request = contract.example_request()
    request["state"]["declared_change_type"] = "bug"
    path.write_text(json.dumps(request))
    assert cli.main(["decide", str(path)]) == 4
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "audit_unavailable"
    monkeypatch.setenv("S1_HOME", str(tmp_path / "good"))
    assert cli.main(["decide", str(tmp_path / "absent")]) == 4
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "input_unavailable"
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(request).encode())))
    assert cli.main(["decide", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["outcomes"][0]["status"] == "answered_rule"


@pytest.mark.requirement("L1-004")
def test_hostile_telemetry_is_reported(tmp_path: Path) -> None:
    from s1router.telemetry import EventStore

    store = EventStore(tmp_path)
    path = tmp_path / "events.jsonl"
    for raw in [
        "[" * 10000 + "]" * 10000,
        json.dumps(
            {
                "timestamp": 10**400,
                "release_id": "a",
                "status": "error",
                "reason": None,
                "duration_ms": 0,
            }
        ),
    ]:
        path.write_text(raw + "\n")
        assert store.observe()["findings"] == ["telemetry_corrupt"]
        with pytest.raises(OSError):
            store.health()
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(OSError):
        store.append("answered_rule", None, 0, "a")


@pytest.mark.requirement("L1-005")
def test_invalid_release_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from s1router.cli import main

    monkeypatch.setenv("S1_HOME", str(tmp_path))
    monkeypatch.setenv("S1_RELEASE_ID", "bad/id")
    assert main(["doctor"]) == 4
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_configuration"


@pytest.mark.requirement("L1-004")
def test_incidents_deduplicate_each_finding_and_disclose_history(tmp_path: Path) -> None:
    from s1router.telemetry import EventStore

    store = EventStore(tmp_path)
    (tmp_path / "events.jsonl").write_text("corrupt\n")
    first = store.record_incident(store.observe(), "release")
    for _ in range(20):
        store.append("answered_rule", None, 20, "release")
    store.record_incident(store.observe(), "release")
    records = list((tmp_path / "incidents").glob("*.md"))
    assert len(records) == 2
    assert sum("Findings: telemetry_corrupt" in p.read_text() for p in records) == 1
    assert first is not None and "(#repair-procedure)" in first.read_text()
    assert store.observe()["history_complete"] is False
