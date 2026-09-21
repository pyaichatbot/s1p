"""Provider and audit contracts shared by SDK composition and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from s1router.domain.acceptance import CalibrationProfile
from s1router.domain.capabilities import Capabilities

PROVIDER_FAILURES = frozenset(
    {
        "artifact_missing",
        "artifact_corrupt",
        "incompatible_runtime",
        "inference_failed",
        "provider_unavailable",
    }
)


class ProviderFailure(RuntimeError):
    """Sanitized operational failure carrying only a registered reason."""

    def __init__(self, code: str) -> None:
        if code not in PROVIDER_FAILURES:
            raise ValueError("invalid_provider_output")
        self.code = code
        self.transient = code == "provider_unavailable"
        super().__init__(code)


@dataclass(frozen=True)
class ProviderReply:
    prediction: dict[str, Any] | None = None
    selected_id: str | None = None
    actual_cost_usd: str | None = None


class DecisionProvider(Protocol):
    provider_id: str
    remote: bool
    endpoint: str | None
    max_cost_usd: str
    capabilities: Capabilities | None
    calibration: CalibrationProfile | None

    def count_tokens(self, text: str) -> int: ...

    def evaluate(
        self, request: dict[str, Any], question: dict[str, Any], timeout_seconds: float
    ) -> ProviderReply:
        """Return before timeout or terminate execution and raise TimeoutError.

        Production adapters must enforce this bound using a killable process or
        bounded transport. Cancelling a Python await alone does not satisfy it.
        A provider must never mutate the request or perform downstream actions.
        """
        ...


class AuditSink(Protocol):
    def append(self, record: dict[str, Any]) -> str:
        """Persist one redacted record atomically or raise OSError."""
        ...
