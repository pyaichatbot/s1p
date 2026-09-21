"""M-004: training/build report of code, data, environment and checkpoint identity.

This repository has no gradient-descent training loop yet (see
``s1m.inference.linear.SparseLinear``): current bundles are hand-authored,
fixture-style sparse weight sets, not the output of an optimizer fitting a
loss. This module therefore does not fabricate optimizer/loss claims; the
``optimizer`` field records the honest provenance value for how the
checkpoint's weights were produced (e.g. ``"closed-form"`` or
``"hand-authored-fixture"``), and ``seed`` records the deterministic seed
used wherever a stochastic step exists, or an explicit ``"n/a"``-style
constant when none does.

Computing the digests themselves (hashing source trees, training data,
pinned dependency locks) is a build/CLI concern, deliberately out of scope
here: this module takes already-computed digests as explicit typed inputs,
validates their shape, and produces a deterministic, canonically
serializable report -- following the same sha256-of-content identity
convention used throughout the repository (``s1m.artifacts.manifest``,
``s1_contracts.capabilities.RegisteredTask.reference``,
``s1router.domain.acceptance.CalibrationProfile``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_DIGEST = re.compile(r"[a-f0-9]{64}")

#: Field name -> "is a content digest" (validated as 64 lowercase hex chars)
#: versus "is a free-text identity" (validated as non-empty, non-blank text).
_DIGEST_FIELDS = ("code_digest", "data_digest", "checkpoint_digest")
_TEXT_FIELDS = ("environment_id", "seed", "optimizer")


class TrainingReportError(ValueError):
    """Raised when a training report input is missing or malformed."""


def _require_digest(field: str, value: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise TrainingReportError(f"{field}: expected a 64-hex-character sha256 digest")
    return value


def _require_text(field: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrainingReportError(f"{field}: expected non-empty, non-blank text")
    return value


@dataclass(frozen=True, slots=True)
class TrainingReport:
    """A validated, serializable record of what produced a model artifact."""

    code_digest: str
    data_digest: str
    environment_id: str
    seed: str
    optimizer: str
    checkpoint_digest: str

    def __post_init__(self) -> None:
        for field in _DIGEST_FIELDS:
            _require_digest(field, getattr(self, field))
        for field in _TEXT_FIELDS:
            _require_text(field, getattr(self, field))

    def canonical_json(self) -> str:
        """A deterministic, sorted-key JSON serialization of this report."""
        fields = {name: getattr(self, name) for name in self.__slots__}
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_training_report(
    *,
    code_digest: str,
    data_digest: str,
    environment_id: str,
    seed: str,
    optimizer: str,
    checkpoint_digest: str,
) -> TrainingReport:
    """Validate explicit build inputs and produce a ``TrainingReport``.

    Raises ``TrainingReportError`` naming the first missing or malformed
    field. All six inputs must be supplied by the caller (typically a build
    CLI that actually computed the digests); this function performs no
    filesystem or process introspection of its own.
    """
    return TrainingReport(
        code_digest=code_digest,
        data_digest=data_digest,
        environment_id=environment_id,
        seed=seed,
        optimizer=optimizer,
        checkpoint_digest=checkpoint_digest,
    )
