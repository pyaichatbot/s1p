"""Explicit export of an experimental sparse candidate; never executed by scoring."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from s1_contracts.capabilities import RegisteredTask
from s1m.artifacts.manifest import MAX_FILE_BYTES, load
from s1m.inference.linear import SparseLinear


def export_candidate(
    destination: Path, *, weights: dict[str, Any], task: dict[str, Any], license_text: str
) -> str:
    """Create a new directory exclusively; a partial export cannot pass bundle verification.

    Dataset/weight redistribution rights remain the caller's reviewed responsibility.
    Exporting never assigns calibration or approval to the resulting identity.
    """
    registered = RegisteredTask.create(task)
    labels = [entry["id"] for entry in registered.definition["support"]]
    SparseLinear(weights, labels)
    if not isinstance(license_text, str) or not license_text.strip():
        raise ValueError("invalid_configuration")
    values = {
        "weights.json": weights,
        "tokenizer.json": {"type": "unicode-codepoint-v1"},
        "preprocessor.json": {"type": "unicode-word-count-v1", "fields": ["title", "body"]},
    }
    if not {"title", "body"} <= set(registered.definition["state_schema"]):
        raise ValueError("invalid_configuration")
    payloads = {
        name: json.dumps(value, sort_keys=True, allow_nan=False).encode()
        for name, value in values.items()
    }
    payloads["LICENSE.txt"] = license_text.encode()
    if any(len(data) > MAX_FILE_BYTES for data in payloads.values()):
        raise ValueError("artifact_corrupt")
    manifest = {
        "format": "s1m.bundle.v1",
        "contract_version": "1.0",
        "precision": "fp64",
        "runtime": "python-stdlib-v1",
        "task": registered.definition,
        "status": "experimental_candidate",
        "files": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
            for name, data in payloads.items()
        },
    }
    payloads["manifest.json"] = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    destination.mkdir(mode=0o700)  # never overwrite an existing artifact
    for name, data in payloads.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    return load(destination)[0]
