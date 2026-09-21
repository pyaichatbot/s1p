"""Experimental offline provider with a killable inference process."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import s1_contracts
import s1m
from s1_contracts.capabilities import Capabilities
from s1_contracts.prediction import validate_prediction
from s1_contracts.request import object_fields
from s1m.inference.runtime import LocalRuntime

import s1router
from s1router.domain.acceptance import CalibrationProfile
from s1router.ports.providers import ProviderFailure, ProviderReply

MAX_REPLY_BYTES = 512 * 1024
BOOTSTRAP = (
    "import json, sys; sys.path[:0] = json.loads(sys.argv.pop(1)); "
    "from s1router.adapters.local_worker import main; raise SystemExit(main())"
)


def package_root(module: ModuleType) -> str:
    if module.__file__ is None:
        raise ValueError("incompatible_runtime")
    return str(Path(module.__file__).resolve().parent.parent)


class LocalProvider:
    remote = False
    endpoint: str | None = None
    max_cost_usd = "0.000000"
    calibration: CalibrationProfile | None = None
    provider_id = "s1m-sparse"
    capabilities: Capabilities | None

    def __init__(self, installed: Path) -> None:
        runtime = LocalRuntime(installed)
        self.installed = installed.resolve()
        self.reference = runtime.provenance["model_ref"]
        self.capabilities = runtime.capabilities

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(text)

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise TimeoutError("deadline_exceeded")
        payload = json.dumps(request | {"questions": [question]}, allow_nan=False).encode()
        try:
            # The trusted worker writes one bounded frame. subprocess.run kills
            # and waits for this child on timeout; the worker starts no children.
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    BOOTSTRAP,
                    json.dumps([package_root(module) for module in (s1_contracts, s1router, s1m)]),
                    str(self.installed),
                    self.reference,
                ],
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("deadline_exceeded") from exc
        if len(result.stdout) > MAX_REPLY_BYTES:
            raise ValueError("invalid_provider_output")
        payload = json.loads(result.stdout)
        if result.returncode:
            error = object_fields(object_fields(payload, {"error"})["error"], {"code"})
            raise ProviderFailure(error["code"])
        prediction = validate_prediction(payload, question)
        if prediction["provenance"]["model_ref"] != self.reference:
            raise ValueError("artifact_corrupt")
        return ProviderReply(prediction=prediction)
