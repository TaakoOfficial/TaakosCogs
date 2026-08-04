"""Enforce release metadata policy for cog changes in pull requests."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


def discover_cogs(root: Path) -> set[str]:
    """Return installable top-level cog directories."""
    return {path.parent.name for path in root.glob("*/info.json") if (path.parent / "__init__.py").is_file()}


def is_runtime_path(path: str, cog: str) -> bool:
    """Return whether a changed cog path can alter installed runtime behavior."""
    parts = PurePosixPath(path).parts
    if not parts or parts[0] != cog or len(parts) < 2:
        return False
    relative = PurePosixPath(*parts[1:])
    if relative.name in {"README.md", "CHANGELOG.md", "info.json"}:
        return False
    if relative.parts[0] in {"docs", "wiki"}:
        return False
    return "__pycache__" not in relative.parts and relative.suffix not in {".md", ".pot"}


def parse_version(value: Any) -> tuple[int, int, int] | None:
    """Parse the repository's required three-component cog versions."""
    try:
        parts = tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return None
    return parts if len(parts) == 3 else None


def validate_changes(
    root: Path,
    changed_files: list[str],
    base_info: dict[str, dict[str, Any] | None],
) -> list[str]:
    """Return human-readable policy violations for the supplied diff."""
    violations: list[str] = []
    changed = {PurePosixPath(path).as_posix() for path in changed_files}
    for cog in sorted(discover_cogs(root)):
        cog_changes = [path for path in changed if PurePosixPath(path).parts[:1] == (cog,)]
        if not cog_changes:
            continue

        current_path = root / cog / "info.json"
        current = json.loads(current_path.read_text(encoding="utf-8"))
        current_version = parse_version(current.get("version"))
        previous = base_info.get(cog)
        if previous is None:
            if not (root / cog / "README.md").is_file():
                violations.append(f"{cog}: new cogs require a README.md")
            continue

        previous_version = parse_version(previous.get("version"))
        if current_version is None or previous_version is None:
            violations.append(f"{cog}: versions must use MAJOR.MINOR.PATCH")
            continue
        if current_version < previous_version:
            violations.append(
                f"{cog}: version decreased from {previous['version']} to {current['version']}",
            )
            continue

        runtime_changed = any(is_runtime_path(path, cog) for path in cog_changes)
        if runtime_changed and current_version == previous_version:
            violations.append(
                f"{cog}: runtime files changed without bumping info.json version above {previous['version']}",
            )
    return violations


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def base_cog_info(root: Path, base: str, cogs: set[str]) -> dict[str, dict[str, Any] | None]:
    """Load cog metadata as it existed at the pull request base."""
    result: dict[str, dict[str, Any] | None] = {}
    for cog in cogs:
        show = subprocess.run(
            ["git", "show", f"{base}:{cog}/info.json"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        result[cog] = json.loads(show.stdout) if show.returncode == 0 else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    changed_files = git_output(root, "diff", "--name-only", args.base, args.head, "--").splitlines()
    cogs = discover_cogs(root)
    violations = validate_changes(root, changed_files, base_cog_info(root, args.base, cogs))
    if violations:
        print("Cog release policy failed:")
        for violation in violations:
            print(f"- {violation}")
        raise SystemExit(1)
    print("Cog release metadata policy passed.")


if __name__ == "__main__":
    main()
