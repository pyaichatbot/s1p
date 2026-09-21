"""File-backed audit sink: append-only, redacted, one record per line.

Design: docs/s1router/design.md#deployment-resources-and-operations. Router
records passed here already carry no raw request/state text (see
``s1router.application.engine.Router.decide``); this adapter never adds any.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any

MAX_RECORD_BYTES = 64 * 1024
MAX_SEGMENT_BYTES = 8 * 1024 * 1024


def _open(path: Path, flags: int) -> int:
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(fd, 0o600)
    return fd


class FileAuditSink:
    """Append one JSON line per decision; the reference is the line's own hash.

    A single append-only segment, bounded so an unbounded audit trail can
    never exhaust disk during the request path: once the segment reaches
    ``MAX_SEGMENT_BYTES`` every further append raises OSError, matching the
    protocol's "or raise OSError" contract, rather than truncating or
    silently dropping evidence.
    """

    def __init__(self, directory: Path) -> None:
        if directory.is_symlink():
            raise OSError("Unsafe audit directory")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.path = directory / "audit.jsonl"

    def append(self, record: dict[str, Any]) -> str:
        data = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(data) > MAX_RECORD_BYTES:
            raise OSError("audit record too large")
        reference = hashlib.sha256(data).hexdigest()
        fd = _open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, "wb", buffering=0) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            original_size = os.fstat(stream.fileno()).st_size
            if original_size + len(data) > MAX_SEGMENT_BYTES:
                raise OSError("audit segment full; requires operator rotation")
            try:
                remaining = memoryview(data)
                while remaining:
                    written = os.write(stream.fileno(), remaining)
                    if written <= 0:
                        raise OSError("audit write made no progress")
                    remaining = remaining[written:]
                os.fsync(stream.fileno())
            except OSError:
                os.ftruncate(stream.fileno(), original_size)
                raise
        return reference
