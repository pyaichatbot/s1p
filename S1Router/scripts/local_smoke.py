"""Exercise the installed command from outside the checkout using synthetic inputs."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from scripts.check_repo import ROOT, require


def main() -> int:
    launcher = ROOT / ".local/s1/bin/s1"
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(launcher), *args], cwd=directory, text=True, capture_output=True, check=False
            )

        example = run("example")
        require(example.returncode == 0, "Installed example failed")
        request = json.loads(example.stdout)
        path = directory / "input.json"
        path.write_text(json.dumps(request))
        require(run("decide", str(path)).returncode == 3, "Abstention failed")
        request["state"]["declared_change_type"] = "bug"
        path.write_text(json.dumps(request))
        require(run("decide", str(path)).returncode == 0, "Rule failed")
        path.write_text("not JSON")
        require(run("decide", str(path)).returncode == 2, "Invalid input failed")
        require(run("doctor").returncode == 0, "Doctor failed")
        observed = run("observe")
        require(observed.returncode == 0, "Observation found an issue")
        print(observed.stdout.strip())
        print("PASS: installed command smoke from temporary working directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
