"""M-009/M-010: trained candidates install offline without inheriting release status."""

from pathlib import Path

import pytest
from s1_contracts.request import example_request, task_definition
from s1m.artifacts.bundle import install
from s1m.inference.runtime import LocalRuntime

pytestmark = [pytest.mark.behavioral, pytest.mark.integration]


@pytest.mark.requirement("M-009")
@pytest.mark.requirement("M-010")
def test_exported_candidate_is_verified_offline_and_never_automatically_released(
    tmp_path: Path,
) -> None:
    from s1m.artifacts.export import export_candidate

    weights = {
        "format": "s1m.sparse-linear.v1",
        "labels": ["bug", "feature", "documentation", "refactor"],
        "bias": [0.0] * 4,
        "features": {"fix": [3.0, 0.0, 0.0, 0.0]},
    }
    source = tmp_path / "candidate"
    reference = export_candidate(
        source, weights=weights, task=task_definition(), license_text="CC0 fixture"
    )
    assert install(source, tmp_path / "installed") == reference
    prediction = LocalRuntime(tmp_path / "installed").predict(example_request())[0]
    assert prediction["selected_id"] == "bug"
    assert prediction["calibration_status"] == "raw"
    assert prediction["provenance"]["model_ref"] == reference
    with pytest.raises(FileExistsError):
        export_candidate(
            source, weights=weights, task=task_definition(), license_text="CC0 fixture"
        )
