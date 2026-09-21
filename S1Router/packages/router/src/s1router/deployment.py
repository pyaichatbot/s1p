"""Content-verified local snapshots and atomic active-pointer changes."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_id(files: dict[str, str]) -> str:
    return digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def valid_name(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and path.suffix == ".py"


def verify(path: Path) -> str:
    """Integrity, not authenticity: local owner controls install and manifest."""
    try:
        root = path.resolve(strict=True)
        manifest_path = root / "manifest.json"
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024 * 1024:
            raise ValueError("integrity")
        manifest = json.loads(manifest_path.read_text())
        files = manifest["files"]
        if not isinstance(files, dict) or not files or len(files) > 1000:
            raise ValueError("integrity")
        actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
        if actual != set(files) | {"manifest.json"}:
            raise ValueError("integrity")
        if any(p.is_symlink() for p in root.rglob("*")):
            raise ValueError("integrity")
        for name, expected in files.items():
            if not valid_name(name) or digest((root / name).read_bytes()) != expected:
                raise ValueError("integrity")
        release_id = manifest_id(files)
        if manifest["release_id"] != release_id:
            raise ValueError("integrity")
        return release_id
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        raise ValueError("release_integrity_failure") from exc


@contextmanager
def locked(destination: Path) -> Iterator[None]:
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def point(destination: Path, name: str, target: Path) -> None:
    temporary = destination / f".{name}.{os.getpid()}"
    try:
        temporary.symlink_to(target)
        temporary.replace(destination / name)
    finally:
        temporary.unlink(missing_ok=True)


def activate(destination: Path, release: Path) -> None:
    verify(release)
    active = destination / "active"
    if active.exists():
        previous = active.resolve()
        verify(previous)
        if previous == release.resolve():
            return
        point(destination, "previous", previous)
    point(destination, "active", release.resolve())


def deploy(sources: dict[str, Path], destination: Path) -> str:
    if not sources or not all(valid_name(name) for name in sources):
        raise ValueError("invalid_sources")
    content = {name: path.read_bytes() for name, path in sources.items()}
    files = {name: digest(data) for name, data in content.items()}
    release_id = manifest_id(files)
    with locked(destination):
        releases = destination / "releases"
        releases.mkdir(exist_ok=True)
        release = releases / release_id
        if not release.exists():
            staging = Path(tempfile.mkdtemp(prefix=".stage-", dir=releases))
            try:
                for name, data in content.items():
                    path = staging / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                (staging / "manifest.json").write_text(
                    json.dumps({"release_id": release_id, "files": files}, sort_keys=True)
                )
                verify(staging)
                staging.rename(release)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        activate(destination, release)
    return release_id


def rollback(destination: Path) -> str:
    with locked(destination):
        previous = destination / "previous"
        release_id = verify(previous)
        target = previous.resolve()
        try:
            verify(destination / "active")
        except ValueError:
            point(destination, "active", target)
        else:
            activate(destination, target)
        return release_id


# The launcher is deliberately self-contained and imports only verified snapshot code.
LAUNCHER = """#!{python}
import hashlib, json, os, pathlib, sys
sys.dont_write_bytecode = True
base = pathlib.Path(__file__).resolve().parents[1]
try:
    root = (base / "active").resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text())
    files = manifest["files"]
    if not files or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError()
    actual = {{str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}}
    if actual != set(files) | {{"manifest.json"}}:
        raise ValueError()
    for name, expected in files.items():
        p = pathlib.Path(name)
        if p.is_absolute() or ".." in p.parts or p.suffix != ".py":
            raise ValueError()
        if hashlib.sha256((root / p).read_bytes()).hexdigest() != expected:
            raise ValueError()
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    identity = hashlib.sha256(encoded).hexdigest()
    if identity != manifest["release_id"]:
        raise ValueError()
except (OSError, ValueError, KeyError, TypeError, RecursionError):
    print(json.dumps({{"error": {{"code": "release_integrity_failure"}}}}))
    sys.exit(4)
sys.path[:0] = [str(root / name) for name in ("contracts", "router", "model")]
os.environ.setdefault("S1_HOME", str(base / "state"))
os.environ["S1_RELEASE_ID"] = identity
from s1router.cli import main
sys.exit(main())
"""


def install(root: Path, destination: Path) -> str:
    sources = {
        str(Path(package.name) / path.relative_to(package / "src")): path
        for package in (root / "packages").iterdir()
        for path in (package / "src").rglob("*.py")
    }
    release_id = deploy(sources, destination)
    binary = destination / "bin"
    binary.mkdir(exist_ok=True)
    temporary = binary / f".s1.{os.getpid()}"
    temporary.write_text(LAUNCHER.format(python=sys.executable))
    temporary.chmod(0o755)
    temporary.replace(binary / "s1")
    return release_id


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["deploy", "rollback", "status"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    destination = args.destination or args.root / ".local/s1"
    try:
        if args.command == "deploy":
            release = install(args.root, destination)
        elif args.command == "rollback":
            release = rollback(destination)
        else:
            release = verify(destination / "active")
        print(json.dumps({"status": "verified", "release_id": release}))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "reason": type(exc).__name__}))
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised only as a real subprocess
    raise SystemExit(main())
