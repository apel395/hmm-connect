"""Validate the Alembic revision graph without importing application models.

This check is intentionally dependency-free so it can run in GitHub Actions and
on the EC2 administration host before any production migration is attempted.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
REVISION_RE = re.compile(r"^Revision ID:\s*(\S+)", re.MULTILINE)
REVISES_RE = re.compile(r"^Revises:\s*(\S+)", re.MULTILINE)


@dataclass(frozen=True)
class Revision:
    revision: str
    down_revision: str | None
    path: Path
    documented_revision: str | None
    documented_parent: str | None


def literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"missing {name!r} assignment")


def load_revision(path: Path) -> Revision:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    revision = literal_assignment(tree, "revision")
    down_revision = literal_assignment(tree, "down_revision")

    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("revision must be a non-empty string")
    if down_revision is not None and not isinstance(down_revision, str):
        raise ValueError("merge/multiple-parent revisions are not supported in this repository")

    docstring = ast.get_docstring(tree) or ""
    documented_revision = REVISION_RE.search(docstring)
    documented_parent = REVISES_RE.search(docstring)
    return Revision(
        revision=revision,
        down_revision=down_revision,
        path=path,
        documented_revision=documented_revision.group(1) if documented_revision else None,
        documented_parent=documented_parent.group(1) if documented_parent else None,
    )


def main() -> None:
    errors: list[str] = []
    revisions: dict[str, Revision] = {}

    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        try:
            item = load_revision(path)
        except (SyntaxError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        if item.revision in revisions:
            errors.append(
                f"duplicate revision {item.revision}: "
                f"{revisions[item.revision].path.name}, {path.name}"
            )
        revisions[item.revision] = item

        if item.documented_revision and item.documented_revision != item.revision:
            errors.append(
                f"{path.name}: docstring Revision ID {item.documented_revision} "
                f"does not match revision {item.revision}"
            )
        if item.documented_parent:
            expected = item.down_revision or "None"
            if item.documented_parent != expected:
                errors.append(
                    f"{path.name}: docstring Revises {item.documented_parent} "
                    f"does not match down_revision {expected}"
                )

    children: dict[str, list[str]] = {key: [] for key in revisions}
    for item in revisions.values():
        if item.down_revision is None:
            continue
        if item.down_revision not in revisions:
            errors.append(
                f"{item.path.name}: missing parent revision {item.down_revision}"
            )
            continue
        children[item.down_revision].append(item.revision)

    roots = sorted(item.revision for item in revisions.values() if item.down_revision is None)
    heads = sorted(key for key, value in children.items() if not value)

    if len(roots) != 1:
        errors.append(f"expected exactly one migration root, found {roots}")
    if len(heads) != 1:
        errors.append(f"expected exactly one migration head, found {heads}")

    for parent, values in children.items():
        if len(values) > 1:
            errors.append(f"branch detected at {parent}: children={sorted(values)}")

    if errors:
        print("Migration chain validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(
        f"Migration chain valid: {len(revisions)} revisions, "
        f"root={roots[0]}, head={heads[0]}"
    )


if __name__ == "__main__":
    main()
