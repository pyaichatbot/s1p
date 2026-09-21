"""Offline scoring for the experimental sparse linear baseline.

Training produces weights; explicit installation verifies them before serving.
This module only computes predictions. It never trains or downloads on a request.
Experimental status reflects missing model-quality evidence, not offline operation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from s1_contracts.prediction import finite
from s1_contracts.request import object_fields


class SparseLinear:
    def __init__(self, weights: dict[str, Any], labels: list[str]) -> None:
        value = object_fields(weights, {"format", "labels", "bias", "features"})
        if value["format"] != "s1m.sparse-linear.v1" or value["labels"] != labels:
            raise ValueError("artifact_corrupt")
        self.bias = self._vector(value["bias"], len(labels))
        features = value["features"]
        if not isinstance(features, dict) or len(features) > 100_000:
            raise ValueError("artifact_corrupt")
        self.features = {}
        for term, vector in features.items():
            if (
                not isinstance(term, str)
                or re.fullmatch(r"\w{1,128}", term) is None
                or term != term.lower()
            ):
                raise ValueError("artifact_corrupt")
            self.features[term] = self._vector(vector, len(labels))

    @staticmethod
    def _vector(value: Any, width: int) -> tuple[float, ...]:
        if (
            not isinstance(value, list)
            or len(value) != width
            or not all(finite(item, -1e6, 1e6) for item in value)
        ):
            raise ValueError("artifact_corrupt")
        return tuple(float(item) for item in value)

    def probabilities(self, text: str) -> list[float]:
        counts = Counter(re.findall(r"\w+", text.lower()))
        logits = [
            math.fsum(
                [bias]
                + [
                    self.features[term][i] * count
                    for term, count in counts.items()
                    if term in self.features
                ]
            )
            for i, bias in enumerate(self.bias)
        ]
        maximum = max(logits)
        exponents = [math.exp(logit - maximum) for logit in logits]
        total = math.fsum(exponents)
        return [value / total for value in exponents]
