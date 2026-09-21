"""Offline experimental baseline with typed, uncalibrated predictions."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from s1_contracts.capabilities import Capabilities, RegisteredTask
from s1_contracts.prediction import validate_prediction
from s1_contracts.request import parse_request

from s1m.artifacts.bundle import load_pointer, release_path
from s1m.artifacts.manifest import decode, load
from s1m.inference.linear import SparseLinear


class LocalRuntime:
    """Load verified bytes once; all subsequent inference is in memory."""

    def __init__(
        self,
        installed: Path,
        *,
        bundle_reference: str | None = None,
        max_state_tokens: int = 32_768,
        max_head_tokens: int = 16_384,
    ) -> None:
        if bundle_reference is not None and re.fullmatch(r"[a-f0-9]{64}", bundle_reference) is None:
            raise ValueError("artifact_corrupt")
        if bundle_reference is None:
            reference, manifest, files = load_pointer(installed, "active")
        else:
            bundle = release_path(installed, bundle_reference)
            reference, manifest, files = load(bundle)
            if reference != bundle_reference:
                raise ValueError("artifact_corrupt")
        self.task = RegisteredTask.create(manifest["task"])
        self.capabilities = Capabilities(
            (self.task,),
            tuple(self.task.definition["languages"]),
            max_state_tokens,
            max_head_tokens,
            32,
            64,
        )
        self.model = SparseLinear(
            decode(files["weights.json"]), [item["id"] for item in self.task.definition["support"]]
        )
        self.fields = tuple(decode(files["preprocessor.json"])["fields"])
        self.provenance = {
            "provider_id": "s1m-sparse",
            "model_ref": reference,
            "tokenizer_hash": manifest["files"]["tokenizer.json"]["sha256"],
            "preprocessor_hash": manifest["files"]["preprocessor.json"]["sha256"],
            "definition_hash": self.task.reference,
            "precision": "fp64",
            "runtime_version": "python-stdlib-v1",
            "calibration_ref": None,
        }

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(text)

    def predict(self, value: dict[str, Any]) -> list[dict[str, Any]]:
        request = parse_request(json.dumps(value, allow_nan=False).encode())
        return [self._predict(request, question) for question in request["questions"]]

    def _predict(self, request: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
        reason = self.capabilities.check(request, question, self.count_tokens)
        result: dict[str, Any] = {
            "question_id": question["id"],
            "status": "unsupported" if reason else "predicted",
            "reason": reason,
            "calibration_status": "unavailable" if reason else "raw",
            "provenance": dict(self.provenance),
            "probabilities": None,
            "selected_id": None,
            "confidence": None,
            "p_true": None,
            "expected_value": None,
        }
        if reason:
            return validate_prediction(result, question)
        text = "\n".join(request["state"].get(field, "") for field in self.fields)
        probabilities = self.model.probabilities(text)
        support = question["support"]
        selected = max(range(len(probabilities)), key=probabilities.__getitem__)
        result.update(
            probabilities=[
                {"id": item["id"], "probability": probability}
                for item, probability in zip(support, probabilities, strict=True)
            ],
            selected_id=support[selected]["id"],
            confidence=probabilities[selected],
            p_true=probabilities[1] if question["kind"] == "bool" else None,
            expected_value=math.fsum(
                item["value"] * probability
                for item, probability in zip(support, probabilities, strict=True)
            )
            if question["kind"] == "score"
            else None,
        )
        return validate_prediction(result, question)
