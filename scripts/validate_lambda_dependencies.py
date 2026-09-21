"""Reject worker-only dependencies from the AWS Lambda runtime package."""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
BLOCKED_MODULES = {"openpyxl", "pandas", "xlsxwriter", "xlrd", "xlwt", "pyarrow", "polars", "numpy"}
WORKER_ONLY_FILES = {
    Path("scripts/create_historical_import_samples.py"),
    Path("scripts/export_worker.py"),
    Path("scripts/journal_import_worker.py"),
    Path("services/historical_import_service.py"),
}


def imported_root(alias_name: str) -> str:
    return alias_name.split(".", 1)[0]


def main() -> None:
    errors: list[str] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(APP_DIR)
        if relative in WORKER_ONLY_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                root = imported_root(name)
                if root in BLOCKED_MODULES:
                    errors.append(f"{path.relative_to(APP_DIR.parent)}:{node.lineno}: worker-only dependency import {root!r}")
    if errors:
        print("Lambda dependency validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Lambda dependency validation passed: runtime modules contain no worker-only imports")


if __name__ == "__main__":
    main()
