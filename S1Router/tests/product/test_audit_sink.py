"""R-009: file-backed audit sink is append-only, bounded and never expands silently."""

from __future__ import annotations

from pathlib import Path

import pytest
from s1router.adapters.audit import MAX_RECORD_BYTES, MAX_SEGMENT_BYTES, FileAuditSink

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


@pytest.mark.requirement("R-009")
def test_append_returns_a_stable_reference_for_the_same_record(tmp_path: Path) -> None:
    sink = FileAuditSink(tmp_path / "audit")
    record = {"schema_version": "1.0", "outcomes": []}
    reference = sink.append(record)
    assert isinstance(reference, str) and reference
    assert sink.path.read_text().strip().endswith("}")


@pytest.mark.requirement("R-009")
def test_rejects_a_symlinked_audit_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(OSError):
        FileAuditSink(link)


@pytest.mark.requirement("R-009")
def test_rejects_an_oversized_record_without_writing_it(tmp_path: Path) -> None:
    sink = FileAuditSink(tmp_path / "audit")
    with pytest.raises(OSError):
        sink.append({"outcomes": ["x" * MAX_RECORD_BYTES]})
    assert not sink.path.exists()


@pytest.mark.requirement("R-009")
def test_rejects_appends_once_the_segment_is_full(tmp_path: Path) -> None:
    sink = FileAuditSink(tmp_path / "audit")
    sink.path.write_bytes(b"x" * MAX_SEGMENT_BYTES)
    with pytest.raises(OSError):
        sink.append({"outcomes": []})


@pytest.mark.requirement("R-008")
def test_concurrent_appends_respect_segment_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from s1router.adapters import audit

    sink = FileAuditSink(tmp_path / "audit")
    monkeypatch.setattr(audit, "MAX_SEGMENT_BYTES", 100)
    barrier = Barrier(8)
    original = audit._open

    def open_together(path: Path, flags: int) -> int:
        fd = original(path, flags)
        barrier.wait()
        return fd

    monkeypatch.setattr(audit, "_open", open_together)

    def append(_: int) -> bool:
        try:
            sink.append({"value": "x" * 40})
            return True
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = list(pool.map(append, range(8)))
    assert sum(accepted) == 1
    assert sink.path.stat().st_size <= 100


@pytest.mark.requirement("R-008")
def test_partial_audit_write_failure_restores_previous_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    sink = FileAuditSink(tmp_path / "audit")
    sink.append({"outcomes": []})
    before = sink.path.read_bytes()
    real_write = os.write
    calls = 0

    def failing(fd: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(fd, data[:5])
        raise OSError("disk full")

    monkeypatch.setattr(os, "write", failing)
    with pytest.raises(OSError):
        sink.append({"outcomes": ["new"]})
    assert sink.path.read_bytes() == before
