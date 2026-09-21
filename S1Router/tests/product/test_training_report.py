"""M-004: code/data/environment/seed/optimizer/checkpoint digests in report."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

_training_report = pytest.importorskip(
    "s1m.reporting.training_report", reason="M-004 reporting module not yet implemented"
)
TrainingReportError = _training_report.TrainingReportError
build_training_report = _training_report.build_training_report

pytestmark = [pytest.mark.behavioral]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def report(**changes: str) -> Any:
    fields: dict[str, str] = {
        "code_digest": digest("code-tree-v1"),
        "data_digest": digest("train-split-v1"),
        "environment_id": "uv-lock:" + digest("uv.lock"),
        "seed": "42",
        "optimizer": "closed-form",
        "checkpoint_digest": digest("bundle-manifest-v1"),
    }
    fields.update(changes)
    return build_training_report(**fields)


@pytest.mark.requirement("M-004")
def test_valid_inputs_produce_report_with_all_six_identity_fields() -> None:
    built = report()

    assert built.code_digest == digest("code-tree-v1")
    assert built.data_digest == digest("train-split-v1")
    assert built.environment_id == "uv-lock:" + digest("uv.lock")
    assert built.seed == "42"
    assert built.optimizer == "closed-form"
    assert built.checkpoint_digest == digest("bundle-manifest-v1")
    for field in (
        built.code_digest,
        built.data_digest,
        built.environment_id,
        built.seed,
        built.optimizer,
        built.checkpoint_digest,
    ):
        assert isinstance(field, str) and field


@pytest.mark.requirement("M-004")
@pytest.mark.parametrize(
    "field,value",
    [
        ("code_digest", "not-a-digest"),
        ("data_digest", "a" * 63),
        ("checkpoint_digest", "g" * 64),
        ("checkpoint_digest", ""),
        ("environment_id", ""),
        ("environment_id", "   "),
        ("seed", ""),
        ("optimizer", ""),
    ],
)
def test_missing_or_malformed_field_raises_typed_error(field: str, value: str) -> None:
    with pytest.raises(TrainingReportError, match=field):
        report(**{field: value})


@pytest.mark.requirement("M-004")
def test_report_serialization_is_deterministic_across_calls() -> None:
    first = report().canonical_json()
    second = report().canonical_json()

    assert first == second
    assert '"seed":"42"' in first
    assert first != report(seed="7").canonical_json()
