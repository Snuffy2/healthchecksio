"""Update integration version files for a GitHub release."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

CONST_PATH = Path("custom_components/healthchecksio/const.py")
MANIFEST_PATH = Path("custom_components/healthchecksio/manifest.json")
VERSION_NAME = "VERSION"


def get_release_tag() -> str:
    """Return the release tag supplied by the workflow."""
    release_tag = os.environ.get("RELEASE_TAG")
    if not release_tag:
        raise SystemExit("RELEASE_TAG must be set")
    return release_tag


def update_manifest(release_tag: str) -> None:
    """Update the manifest version with the release tag."""
    manifest = json.loads(MANIFEST_PATH.read_text())
    if not isinstance(manifest, dict) or not isinstance(manifest.get("version"), str):
        raise SystemExit("manifest.json must contain a string version field")

    manifest["version"] = release_tag
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def update_const(release_tag: str) -> None:
    """Update the top-level VERSION constant with the release tag."""
    source = CONST_PATH.read_text()
    tree = ast.parse(source, filename=str(CONST_PATH))
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == VERSION_NAME
    ]
    if (
        len(assignments) != 1
        or not isinstance(assignments[0].value, ast.Constant)
        or not isinstance(assignments[0].value.value, str)
    ):
        raise SystemExit("const.py must contain one top-level string VERSION assignment")

    assignment = assignments[0]
    lines = source.splitlines(keepends=True)
    lines[assignment.lineno - 1 : assignment.end_lineno] = [
        f"{VERSION_NAME} = {json.dumps(release_tag)}\n"
    ]
    CONST_PATH.write_text("".join(lines))


def main() -> None:
    """Update all release version files."""
    release_tag = get_release_tag()
    update_manifest(release_tag)
    update_const(release_tag)


if __name__ == "__main__":
    main()
