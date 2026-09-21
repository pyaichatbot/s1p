"""Bounded, signal-aware JSON-lines framing for the resident worker."""

from __future__ import annotations

import os
import select
from collections.abc import Iterator
from threading import Event
from typing import BinaryIO


def frames(stream: BinaryIO, limit: int, stopping: Event) -> Iterator[bytes]:
    """Yield complete lines, with at most ``limit + 1`` bytes retained per frame."""
    try:
        descriptor = stream.fileno()
    except (AttributeError, OSError):
        descriptor = None
    pending = bytearray()
    discarding = False
    while not stopping.is_set():
        if descriptor is None:
            chunk = stream.read(min(64 * 1024, limit + 1 - len(pending)))
        else:
            ready, _, _ = select.select([descriptor], [], [], 0.1)
            if not ready:
                continue
            chunk = os.read(descriptor, min(64 * 1024, limit + 1 - len(pending)))
        if not chunk:
            if pending and not discarding:
                yield bytes(pending[: limit + 1])
            return
        if discarding:
            marker = chunk.find(b"\n")
            if marker < 0:
                continue
            discarding = False
            chunk = chunk[marker + 1 :]
            if not chunk:
                continue
        pending.extend(chunk)
        while True:
            marker = pending.find(b"\n")
            if marker < 0:
                if len(pending) > limit:
                    yield bytes(pending[: limit + 1])
                    pending.clear()
                    discarding = True
                break
            line = bytes(pending[:marker])
            del pending[: marker + 1]
            if len(line) > limit:
                yield line[: limit + 1]
            elif line:
                yield line
