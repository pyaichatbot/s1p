"""Numerical invariants independent of trained fixture quality."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from s1m.inference.linear import SparseLinear

pytestmark = [pytest.mark.behavioral, pytest.mark.requirement("M-005")]


@given(st.lists(st.integers(-1000, 1000), min_size=2, max_size=21), st.integers(-1000, 1000))
@settings(max_examples=100, derandomize=True)
def test_softmax_support_normalization_order_and_translation_invariance(
    biases: list[int], offset: int
) -> None:
    labels = [str(index) for index in range(len(biases))]
    weights = {"format": "s1m.sparse-linear.v1", "labels": labels, "bias": biases, "features": {}}
    model = SparseLinear(weights, labels)
    probabilities = model.probabilities("no known features")
    shifted = SparseLinear(weights | {"bias": [bias + offset for bias in biases]}, labels)
    assert len(probabilities) == len(labels)
    assert all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
    assert math.fsum(probabilities) == pytest.approx(1, abs=1e-12)
    assert max(range(len(biases)), key=biases.__getitem__) == max(
        range(len(probabilities)), key=probabilities.__getitem__
    )
    assert probabilities == pytest.approx(shifted.probabilities("no known features"), abs=1e-12)
    assert probabilities == model.probabilities("no known features")
