"""Real local inference process boundary, artifact pinning and router integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from s1_contracts.capabilities import RegisteredTask
from s1_contracts.request import example_request, task_definition
from s1m.artifacts.bundle import install
from s1router.adapters.local import LocalProvider
from s1router.application.engine import Router
from s1router.domain.policy import PolicySnapshot, default_policy
from test_local_model import write_bundle
from test_router_engine import Audit

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


@pytest.mark.requirement("R-003")
@pytest.mark.requirement("R-004")
@pytest.mark.requirement("R-010")
def test_real_local_provider_preserves_raw_abstention_and_pinned_artifact(tmp_path: Path) -> None:
    root = tmp_path / "installed"
    first = install(write_bundle(tmp_path / "first"), root)
    provider = LocalProvider(root)
    install(write_bundle(tmp_path / "second", strength=5), root)
    config = default_policy() | {"providers": [provider.provider_id], "rules": []}
    router = Router(
        PolicySnapshot.from_dict(config),
        (provider,),
        (RegisteredTask.create(task_definition()),),
        Audit(),
    )
    result = router.decide(json.dumps(example_request()).encode())
    outcome = result["outcomes"][0]
    assert outcome["status"] == "review_required"
    assert outcome["reason"] == "missing_calibration"
    assert outcome["prediction"]["provenance"]["model_ref"] == first
    assert outcome["selected_id"] is None


@pytest.mark.requirement("R-006")
def test_local_process_timeout_is_terminated_and_reaped(tmp_path: Path, monkeypatch: Any) -> None:
    import subprocess

    root = tmp_path / "installed"
    install(write_bundle(tmp_path / "source"), root)
    provider = LocalProvider(root)
    real_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def spawn(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spawn)
    request = example_request()
    with pytest.raises(TimeoutError):
        provider.evaluate(request, request["questions"][0], 0.000001)
    assert len(children) == 1
    assert children[0].poll() is not None


@pytest.mark.requirement("R-006")
@pytest.mark.requirement("R-010")
def test_worker_protocol_rejects_invalid_frames_and_returns_one_prediction(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import io
    import sys

    from s1router.adapters.local_worker import main

    root = tmp_path / "installed"
    reference = install(write_bundle(tmp_path / "source"), root)
    monkeypatch.setattr(sys, "argv", ["worker"])
    assert main() == 2
    monkeypatch.setattr(sys, "argv", ["worker", str(root), reference])
    for payload in (b"{}", b"x" * (256 * 1024 + 1)):
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
        assert main() == 2
    request = example_request()
    request["questions"].append(request["questions"][0] | {"id": "second"})
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(request).encode())))
    assert main() == 2
    output = io.BytesIO()
    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(example_request()).encode()))
    )
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(output))
    assert main() == 0
    result = json.loads(output.getvalue())
    assert result["status"] == "predicted"
    assert result["provenance"]["model_ref"] == reference
    assert "Fix crash" not in output.getvalue().decode()


@pytest.mark.requirement("R-010")
def test_installed_provider_runs_without_checkout_paths_or_writing_release(
    tmp_path: Path,
) -> None:
    import os
    import subprocess

    from s1router.deployment import install as deploy
    from s1router.deployment import verify

    repository = Path(__file__).resolve().parents[2]
    destination = tmp_path / "deployment"
    release = deploy(repository, destination)
    model = tmp_path / "model"
    install(write_bundle(tmp_path / "bundle"), model)
    code = (
        "import json, sys; sys.path[:0] = sys.argv[1:4]; "
        "from pathlib import Path; from s1router.adapters.local import LocalProvider; "
        "from s1_contracts.request import example_request; "
        "p=LocalProvider(Path(sys.argv[4])); r=example_request(); "
        "print(json.dumps(p.evaluate(r,r['questions'][0],5).prediction))"
    )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    result = subprocess.run(
        [
            str(Path(".venv/bin/python").resolve()),
            "-I",
            "-B",
            "-c",
            code,
            *[
                str((destination / "active" / name).resolve())
                for name in ("contracts", "router", "model")
            ],
            str(model),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "predicted"
    assert verify(destination / "active") == release


@pytest.mark.requirement("R-010")
@pytest.mark.requirement("M-010")
def test_missing_pinned_bundle_preserves_typed_failure(tmp_path: Path) -> None:
    import shutil

    from s1router.ports.providers import ProviderFailure

    root = tmp_path / "installed"
    reference = install(write_bundle(tmp_path / "source"), root)
    provider = LocalProvider(root)
    shutil.rmtree(root / "releases" / reference)
    request = example_request()
    with pytest.raises(ProviderFailure) as failure:
        provider.evaluate(request, request["questions"][0], 5)
    assert failure.value.code == "artifact_missing"
