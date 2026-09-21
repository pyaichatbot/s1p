"""R-008 replay: report whether supplied evidence reproduces a redacted record.

Design: docs/s1router/design.md#deployment-resources-and-operations —
"Replay can use stored sanitized fixtures or caller-supplied state plus
original artifact hashes; it must identify missing data instead of
pretending a hash reconstructs input." This module never re-executes a
decision from a hash: a redacted audit record never contains raw state, so
there is nothing to feed back into ``Router.decide``. It only compares
hashes and reports what is verified, mismatched, or simply not supplied.
"""

from __future__ import annotations

import hashlib
from typing import Any

from s1_contracts.audit import load_record as load_record
from s1router.domain.policy import PolicySnapshot


def replay(
    record: dict[str, Any], state: bytes, policy_config: dict[str, Any] | None
) -> dict[str, Any]:
    """Report input/policy hash reproducibility for one already-recorded decision."""
    input_status = (
        "verified"
        if hashlib.sha256(state).hexdigest() == record["input_sha256"]
        else "missing_original_input"
    )
    if policy_config is None:
        policy_status = "not_supplied"
    else:
        try:
            policy_status = (
                "verified"
                if PolicySnapshot.from_dict(policy_config).reference == record["policy_ref"]
                else "mismatch"
            )
        except (ValueError, TypeError):
            policy_status = "mismatch"
    return {
        "schema_version": "1.0",
        "input": input_status,
        "policy": policy_status,
        "task_registry": "not_verifiable",
        "record": record,
    }
