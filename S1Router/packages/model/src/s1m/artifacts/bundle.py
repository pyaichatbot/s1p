"""Atomic local activation of verified, content-addressed bundles."""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from s1m.artifacts.manifest import load

POINTERS = frozenset({"active", "previous"})
DIGEST = re.compile(r"[a-f0-9]{64}")


def _error(code: str) -> ValueError:
    return ValueError(code)


def _safe_root(root: Path) -> Path:
    if root.is_symlink():
        raise _error("artifact_corrupt")
    if not root.exists():
        raise _error("artifact_missing")
    if not root.is_dir():
        raise _error("artifact_corrupt")
    try:
        safe = root.resolve(strict=True)
    except OSError as exc:
        raise _error("artifact_corrupt") from exc
    releases = root / "releases"
    if releases.is_symlink():
        raise _error("artifact_corrupt")
    if not releases.exists():
        raise _error("artifact_missing")
    if not releases.is_dir():
        raise _error("artifact_corrupt")
    try:
        if releases.resolve(strict=True) != safe / "releases":
            raise _error("artifact_corrupt")
    except OSError as exc:
        raise _error("artifact_corrupt") from exc
    return safe


def release_path(root: Path, reference: str) -> Path:
    """Resolve a digest-named release without following an escape."""
    safe = _safe_root(root)
    if DIGEST.fullmatch(reference) is None:
        raise _error("artifact_corrupt")
    release = root / "releases" / reference
    if release.is_symlink():
        raise _error("artifact_corrupt")
    if not release.exists():
        raise _error("artifact_missing")
    if not release.is_dir():
        raise _error("artifact_corrupt")
    try:
        if release.resolve(strict=True) != safe / "releases" / reference:
            raise _error("artifact_corrupt")
    except OSError as exc:
        raise _error("artifact_corrupt") from exc
    return release


def load_pointer(root: Path, name: str) -> tuple[str, dict[str, Any], dict[str, bytes]]:
    """Load a pointer only when it names its verified digest release exactly."""
    if name not in POINTERS:
        raise _error("artifact_corrupt")
    safe = _safe_root(root)
    pointer = root / name
    if pointer.is_symlink() is False:
        raise _error("artifact_missing" if not pointer.exists() else "artifact_corrupt")
    try:
        target = pointer.resolve(strict=True)
    except OSError as exc:
        raise _error("artifact_corrupt") from exc
    if target.parent != safe / "releases" or DIGEST.fullmatch(target.name) is None:
        raise _error("artifact_corrupt")
    release = release_path(root, target.name)
    reference, manifest, files = load(release)
    if reference != target.name:
        raise _error("artifact_corrupt")
    try:
        if pointer.resolve(strict=True) != target:
            raise _error("artifact_corrupt")
    except OSError as exc:
        raise _error("artifact_corrupt") from exc
    return reference, manifest, files


def verify(root: Path) -> str:
    if root.name in POINTERS:
        return load_pointer(root.parent, root.name)[0]
    return load(root)[0]


@contextmanager
def locked(root: Path) -> Iterator[None]:
    if root.is_symlink():
        raise _error("artifact_corrupt")
    if root.exists() and not root.is_dir():
        raise OSError(f"root is not a directory: {root}")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(
        os.open(root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "a"
    ) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def point(root: Path, name: str, reference: str) -> None:
    """Replace one pointer atomically; never expose a partially written bundle."""
    if name not in POINTERS:
        raise _error("artifact_corrupt")
    release_path(root, reference)
    with tempfile.TemporaryDirectory(prefix=".pointer-", dir=root) as temporary:
        link = Path(temporary) / "link"
        link.symlink_to(Path("releases") / reference)
        os.replace(link, root / name)
    directory = os.open(root, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def install(source: Path, root: Path) -> str:
    reference, _, files = load(source)
    with locked(root):
        releases = root / "releases"
        if releases.is_symlink():
            raise _error("artifact_corrupt")
        if releases.exists() and not releases.is_dir():
            raise _error("artifact_corrupt")
        releases.mkdir(exist_ok=True, mode=0o700)
        destination = releases / reference
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or verify(destination) != reference:
                raise _error("artifact_corrupt")
        else:
            with tempfile.TemporaryDirectory(prefix=".install-", dir=root) as temporary:
                staged = Path(temporary) / "bundle"
                staged.mkdir(mode=0o700)
                for name, data in files.items():
                    with (staged / name).open("xb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    (staged / name).chmod(0o600)
                if verify(staged) != reference:
                    raise ValueError("artifact_corrupt")
                os.replace(staged, destination)
        active = root / "active"
        if active.exists() or active.is_symlink():
            current = load_pointer(root, "active")[0]
            if current == reference:
                return reference
            point(root, "previous", current)
        point(root, "active", reference)
    return reference


def rollback(root: Path) -> str:
    with locked(root):
        reference = load_pointer(root, "previous")[0]
        point(root, "active", reference)
        return reference
