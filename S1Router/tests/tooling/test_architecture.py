"""Boundary regressions for owner-requested product code constraints."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest


def checker() -> Any:
    try:
        return importlib.import_module("scripts.check_architecture")
    except ModuleNotFoundError:
        pytest.fail("Missing product architecture/file-size gate")


def file(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_physical_line_limit_includes_comments_and_blank_lines(tmp_path: Path) -> None:
    module = checker()
    path = file(tmp_path, "packages/router/src/s1router/a.py", "# explanation\n" * 249)
    module.check(tmp_path)
    path.write_text("# explanation\n" * 250)
    with pytest.raises(ValueError, match="249"):
        module.check(tmp_path)
    path.write_text("\n" * 250)
    with pytest.raises(ValueError):
        module.check(tmp_path)
    path.write_text("x = 1\n")
    file(tmp_path, "packages/model/src/s1m/inference/a.py", "import torch\n")
    module.check(tmp_path)


@pytest.mark.parametrize(
    "path,source",
    [
        ("contracts/src/s1_contracts/a.py", "import s1router\n"),
        ("contracts/src/s1_contracts/a.py", "from torch import Tensor\n"),
        ("router/src/s1router/a.py", "import transformers\n"),
        ("router/src/s1router/domain/a.py", "from pathlib import Path\n"),
        ("router/src/s1router/domain/a.py", "from ..telemetry import EventStore\n"),
        ("router/src/s1router/domain/a.py", "from .. import telemetry\n"),
        ("model/src/s1m/inference/a.py", "from ..training import train\n"),
        ("model/src/s1m/inference/a.py", "from s1m import training\n"),
        ("model/src/s1m/domain/a.py", "import os\n"),
    ],
)
def test_forbidden_imports_fail(tmp_path: Path, path: str, source: str) -> None:
    module = checker()
    file(tmp_path, "packages/" + path, source)
    with pytest.raises(ValueError):
        module.check(tmp_path)


def test_allowed_relative_domain_and_command_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = checker()
    file(
        tmp_path,
        "packages/router/src/s1router/domain/a.py",
        "from . import rules\nfrom s1_contracts import request\n",
    )
    module.check(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert module.main() == 0
    file(tmp_path, "packages/model/src/s1m/big.py", "\n" * 250)
    assert module.main() == 1
