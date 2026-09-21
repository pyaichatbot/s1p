"""Mechanical CQ-001/CQ-002 checks; semantic SOLID review remains mandatory."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ML = {
    "torch",
    "tensorflow",
    "transformers",
    "numpy",
    "scipy",
    "sklearn",
    "mlx",
    "jax",
    "laya",
    "pandas",
    "datasets",
    "tokenizers",
}
PURE = {
    "__future__",
    "typing",
    "dataclasses",
    "enum",
    "math",
    "decimal",
    "collections",
    "functools",
    "itertools",
    "operator",
    "hashlib",
    "json",
    "re",
    "abc",
}
SOURCE_SUFFIXES = {
    ".py",
    ".pyi",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".c",
    ".h",
    ".cpp",
    ".rs",
    ".go",
    ".sh",
}
TRAINING = {"training", "train", "evaluation", "evaluate", "data_preparation"}


def imports(tree: ast.AST, module: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                prefix = module[: -node.level]
                if not prefix:
                    raise ValueError("Relative import escapes package")
                base = ".".join((*prefix, *((node.module or "").split(".") if node.module else ())))
            else:
                base = node.module or ""
            result.append(base)
            result.extend(f"{base}.{alias.name}" for alias in node.names)
    return result


def check(root: Path) -> None:
    for source in sorted((root / "packages").glob("*/src")):
        component = source.parent.name
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            body = path.read_text()
            label = str(path.relative_to(root))
            if len(body.splitlines()) >= 250:
                raise ValueError(f"{label}: maximum 249 physical lines (CQ-001)")
            if path.suffix not in {".py", ".pyi"}:
                raise ValueError(f"{label}: new language needs reviewed architecture rules")
            module = path.relative_to(source).with_suffix("").parts
            for dependency in imports(ast.parse(body, filename=label), module):
                top = dependency.split(".")[0]
                if component == "contracts" and top in ML | {"s1router", "s1m"}:
                    raise ValueError(f"{label}: contract depends on implementation {dependency}")
                if component == "router" and top in ML:
                    raise ValueError(f"{label}: ML dependency belongs behind model port")
                if "domain" in module:
                    own_domain = f"{module[0]}.domain"
                    if top not in PURE | {"s1_contracts"} and not (
                        dependency == own_domain or dependency.startswith(own_domain + ".")
                    ):
                        raise ValueError(f"{label}: domain import forbidden: {dependency}")
                if component == "model" and "inference" in module:
                    if TRAINING & set(dependency.split(".")):
                        raise ValueError(f"{label}: inference cannot depend on training workflow")


def main() -> int:
    try:
        check(ROOT)
    except (ValueError, OSError, SyntaxError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print("PASS: product file size and import boundaries; semantic review still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
