"""Single-frame numerical worker, invoked only by the local provider adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from s1_contracts.request import MAX_BYTES, parse_request
from s1m.inference.runtime import LocalRuntime

from s1router.ports.providers import PROVIDER_FAILURES


def main() -> int:
    try:
        if len(sys.argv) != 3:
            return 2
        request = parse_request(sys.stdin.buffer.read(MAX_BYTES + 1))
        if len(request["questions"]) != 1:
            return 2
        runtime = LocalRuntime(Path(sys.argv[1]), bundle_reference=sys.argv[2])
        result = runtime.predict(request)[0]
        frame = json.dumps(result, allow_nan=False).encode()
        if len(frame) > 512 * 1024:
            return 2
        sys.stdout.buffer.write(frame)
        return 0
    except (ValueError, OSError) as exc:
        code = str(exc) if str(exc) in PROVIDER_FAILURES else "inference_failed"
        sys.stdout.buffer.write(json.dumps({"error": {"code": code}}).encode())
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised only as a real subprocess
    raise SystemExit(main())
