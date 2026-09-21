"""Release/acceptance status cannot be reused across a changed artifact identity (M-011).

Mirrors ``s1_contracts.capabilities.check_task_identity``: a release key
(for example a task_id+task_version or release-channel name) is an
immutable commitment to one exact artifact identity. Re-recording the same
identity under a key already seen is idempotent and allowed. Recording a
*different* artifact identity -- for example, a changed-precision bundle,
which per ``s1m.artifacts.manifest.load`` produces a different manifest
hash because ``manifest.json`` (and therefore its sha256) differs -- under
that same key, without an explicit new key, is an identity violation and
must be rejected rather than silently inheriting the prior release or
acceptance status.
"""

from __future__ import annotations

from typing import Any


def check_release_identity(records: tuple[tuple[Any, str], ...]) -> None:
    """Reject a release_key reused with a differing artifact_identity_reference.

    ``records`` is a sequence of ``(release_key, artifact_identity_reference)``
    pairs, where ``artifact_identity_reference`` is typically the manifest
    hash returned by ``s1m.artifacts.manifest.load``. Raises
    ``ValueError("invalid_configuration")`` the first time one release_key
    is seen paired with two different artifact identity references.
    """
    seen: dict[Any, str] = {}
    for release_key, reference in records:
        if not isinstance(reference, str) or not reference:
            raise ValueError("invalid_configuration")
        prior = seen.get(release_key)
        if prior is not None and prior != reference:
            raise ValueError("invalid_configuration")
        seen[release_key] = reference
