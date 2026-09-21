"""Bounded local metadata, deterministic observation and incident records."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MAX_SEGMENT = 1024 * 1024
RETENTION = 7 * 86400
STATUSES = {"answered_rule", "review_required", "invalid_request", "error"}
REASONS = {
    None,
    "remote_disabled",
    "unsupported_task",
    "unsupported_language",
    "invalid_request",
    "internal_error",
    "audit_unavailable",
}
FIELDS = {"timestamp", "release_id", "status", "reason", "duration_ms"}


def valid_event(event: Any) -> bool:
    if not isinstance(event, dict) or set(event) != FIELDS:
        return False
    return (
        isinstance(event["status"], str)
        and event["status"] in STATUSES
        and (event["reason"] is None or isinstance(event["reason"], str))
        and event["reason"] in REASONS
        and isinstance(event["release_id"], str)
        and re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", event["release_id"]) is not None
        and all(
            type(event[key]) in (int, float)
            and 0 <= event[key] <= 1e15
            and math.isfinite(event[key])
            and event[key] >= 0
            for key in ("timestamp", "duration_ms")
        )
    )


def _open(path: Path, flags: int) -> int:
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(fd, 0o600)
    return fd


class EventStore:
    def __init__(self, directory: Path, max_bytes: int = MAX_SEGMENT) -> None:
        if not 512 <= max_bytes <= MAX_SEGMENT:
            raise ValueError("invalid_configuration")
        if directory.is_symlink():
            raise OSError("Unsafe telemetry directory")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.directory = directory
        self.max_bytes = max_bytes

    @contextmanager
    def _lock(self) -> Iterator[None]:
        fd = _open(self.directory / ".lock", os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _read(self) -> tuple[list[dict[str, Any]], int]:
        events: list[dict[str, Any]] = []
        corrupt = 0
        cutoff = time.time() - RETENTION
        for name in ("events.1.jsonl", "events.jsonl"):
            path = self.directory / name
            try:
                fd = _open(path, os.O_RDONLY)
            except FileNotFoundError:
                continue
            with os.fdopen(fd, "rb") as stream:
                data = stream.read(MAX_SEGMENT + 1)
            if len(data) > MAX_SEGMENT:
                corrupt += 1
                continue
            retained: list[bytes] = []
            expired = False
            for line in data.splitlines(keepends=True):
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    event = None
                if not valid_event(event):
                    corrupt += 1
                    retained.append(line)
                elif event["timestamp"] < cutoff:
                    expired = True
                else:
                    events.append(event)
                    retained.append(line)
            if expired:
                fd = _open(path, os.O_WRONLY | os.O_TRUNC)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(b"".join(retained))
                    stream.flush()
                    os.fsync(stream.fileno())
        return events, corrupt

    def append(self, status: str, reason: str | None, duration_ms: float, release_id: str) -> None:
        event = {
            "timestamp": time.time(),
            "release_id": release_id,
            "status": status,
            "reason": reason,
            "duration_ms": duration_ms,
        }
        if not valid_event(event):
            raise ValueError("invalid_event")
        data = (json.dumps(event, separators=(",", ":")) + "\n").encode()
        with self._lock():
            self._read()
            if any(
                p.exists() and p.stat().st_size > self.max_bytes
                for p in (self.directory / "events.jsonl", self.directory / "events.1.jsonl")
            ):
                raise OSError("Oversized telemetry requires operator repair")
            current = self.directory / "events.jsonl"
            if current.exists() and current.stat().st_size + len(data) > self.max_bytes:
                os.replace(current, self.directory / "events.1.jsonl")
            fd = _open(current, os.O_CREAT | os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())

    def observe(self) -> dict[str, Any]:
        with self._lock():
            events, corrupt = self._read()
        count = len(events)
        counts = {status: sum(e["status"] == status for e in events) for status in sorted(STATUSES)}
        durations = sorted(float(e["duration_ms"]) for e in events)
        p95 = durations[math.ceil(0.95 * count) - 1] if count else None
        findings = ["telemetry_corrupt"] if corrupt else []
        if count >= 20:
            if counts["error"] / count > 0.05:
                findings.append("processing_errors")
            if counts["invalid_request"] / count > 0.20:
                findings.append("invalid_requests")
            if p95 is not None and p95 > 10:
                findings.append("processing_latency")
        return {
            "status": "attention"
            if findings
            else ("observed" if count >= 20 else "insufficient_data"),
            "sample_count": count,
            "counts": counts,
            "processing_p95_ms": p95,
            "corrupt_records": corrupt,
            "findings": findings,
            "window_start": min((e["timestamp"] for e in events), default=None),
            "window_end": max((e["timestamp"] for e in events), default=None),
            "retention_seconds": RETENTION,
            "bounded_history": True,
            "history_complete": False,
            "history_scope": "retained_segments_only",
            "possible_gaps": ["rotation", "retention"],
        }

    def record_incident(self, report: dict[str, Any], release_id: str) -> Path | None:
        if not report["findings"]:
            return None
        paths = [
            self._record_finding(report, release_id, finding) for finding in report["findings"]
        ]
        return paths[0]

    def _record_finding(self, report: dict[str, Any], release_id: str, finding: str) -> Path:
        key = hashlib.sha256(json.dumps([release_id, finding]).encode()).hexdigest()[:16]
        directory = self.directory / "incidents"
        directory.mkdir(exist_ok=True, mode=0o700)
        path = directory / f"{key}.md"
        body = (
            "# Local observation incident\n\nStatus: open\n\n"
            f"Release: {release_id}\n\nFindings: {finding}\n\n"
            f"Samples: {report['sample_count']}; corrupt records: {report['corrupt_records']}.\n\n"
            "Impact: inspect local service evidence before trusting operational health.\n\n"
            "Reproduce: run s1 observe against this state directory. Inspect bounded metadata "
            "locally; do not copy raw request data into this record.\n\n"
            "[Repair procedure](#repair-procedure)\n\n## Repair procedure\n\n"
            "Preserve the damaged metadata in a private operator copy before repair. "
            "Check disk permissions and release integrity with s1 doctor. "
            "For corruption, remove only verified invalid records from the live segments; "
            "never reconstruct missing events or silently mark a gap complete.\n\n"
            "Next: diagnose cause, specify a regression test, make the smallest fix, run the "
            "layer gate, redeploy and record a fresh observation before closing.\n\n"
            "Source: [delivery lifecycle](https://claude.com/blog/the-ai-native-sdlc-playbook).\n"
        )
        try:
            fd = _open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            return path
        with os.fdopen(fd, "w") as stream:
            stream.write(body)
        return path

    def health(self) -> None:
        with self._lock():
            _, corrupt = self._read()
            if corrupt:
                raise OSError("Corrupt telemetry")
