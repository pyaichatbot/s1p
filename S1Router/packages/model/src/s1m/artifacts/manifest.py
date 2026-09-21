"""Bounded, offline bundle validation before activation or inference."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from s1_contracts.capabilities import RegisteredTask
from s1_contracts.request import object_fields

from s1m.inference.linear import SparseLinear

PAYLOADS = {"weights.json", "tokenizer.json", "preprocessor.json", "LICENSE.txt"}
MAX_FILE_BYTES = 16 * 1024 * 1024
TYPED_ERRORS = frozenset({"artifact_missing", "artifact_corrupt", "incompatible_runtime"})


def read_file(path: Path) -> bytes:
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
            raise ValueError("artifact_corrupt")
        data = stream.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("artifact_corrupt")
        return data


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("artifact_corrupt")
        value[key] = item
    return value


def decode(data: bytes) -> dict[str, Any]:
    value = json.loads(data, object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError("artifact_corrupt")
    return value


def load(root: Path) -> tuple[str, dict[str, Any], dict[str, bytes]]:
    """Return a verified in-memory snapshot; callers never re-read payload files."""
    try:
        if root.is_symlink():
            raise ValueError("artifact_corrupt")
        if not root.exists():
            raise ValueError("artifact_missing")
        if set(path.name for path in root.iterdir()) != PAYLOADS | {"manifest.json"}:
            raise ValueError("artifact_corrupt")
        raw = read_file(root / "manifest.json")
        manifest = object_fields(
            decode(raw),
            {"format", "contract_version", "precision", "runtime", "task", "status", "files"},
        )
        if (
            manifest["format"] != "s1m.bundle.v1"
            or manifest["contract_version"] != "1.0"
            or manifest["precision"] != "fp64"
            or manifest["runtime"] != "python-stdlib-v1"
            or manifest["status"] != "experimental_fixture"
        ):
            raise ValueError("incompatible_runtime")
        task = RegisteredTask.create(manifest["task"])
        hashes = object_fields(manifest["files"], PAYLOADS)
        files = {name: read_file(root / name) for name in sorted(PAYLOADS)}
        for name, data in files.items():
            entry = object_fields(hashes[name], {"sha256", "size_bytes"})
            if (
                type(entry["size_bytes"]) is not int
                or len(data) != entry["size_bytes"]
                or hashlib.sha256(data).hexdigest() != entry["sha256"]
            ):
                raise ValueError("artifact_corrupt")
        if not files["LICENSE.txt"].decode("utf-8").strip():
            raise ValueError("artifact_corrupt")
        if decode(files["tokenizer.json"]) != {"type": "unicode-codepoint-v1"}:
            raise ValueError("incompatible_runtime")
        preprocessing = object_fields(decode(files["preprocessor.json"]), {"type", "fields"})
        fields = preprocessing["fields"]
        if (
            preprocessing["type"] != "unicode-word-count-v1"
            or not isinstance(fields, list)
            or not fields
            or any(
                not isinstance(field, str) or field not in task.definition["state_schema"]
                for field in fields
            )
            or len(fields) != len(set(fields))
        ):
            raise ValueError("artifact_corrupt")
        SparseLinear(
            decode(files["weights.json"]), [item["id"] for item in task.definition["support"]]
        )
        files["manifest.json"] = raw
        return hashlib.sha256(raw).hexdigest(), manifest, files
    except ValueError as exc:
        if str(exc) in TYPED_ERRORS:
            raise
        raise ValueError("artifact_corrupt") from exc
    except (OSError, TypeError, KeyError, RecursionError) as exc:
        raise ValueError("artifact_corrupt") from exc
