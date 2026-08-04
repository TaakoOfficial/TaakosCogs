"""Select cog directories affected by a Git diff for Live Cog Load."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path, PurePosixPath

FULL_RETEST_PATHS = frozenset(
    {
        ".github/scripts/changed_cogs.py",
        ".github/workflows/live-cog-load.yml",
        "pyproject.toml",
        "uv.lock",
    },
)


def discover_cogs(root: Path) -> list[str]:
    """Return every installable top-level cog directory."""
    return sorted(path.parent.name for path in root.glob("*/info.json") if (path.parent / "__init__.py").is_file())


def select_changed_cogs(changed_files: list[str], available_cogs: list[str]) -> list[str]:
    """Map changed paths to cogs, expanding shared tooling changes to all cogs."""
    normalized = {PurePosixPath(path).as_posix() for path in changed_files}
    if normalized & FULL_RETEST_PATHS:
        return available_cogs

    available = set(available_cogs)
    selected = {parts[0] for path in normalized if (parts := PurePosixPath(path).parts) and parts[0] in available}
    return sorted(selected)


def git_changed_files(root: Path, base: str, head: str) -> list[str] | None:
    """Return changed files, or None when the requested range is unavailable."""
    if not base or not head or set(base) == {"0"}:
        return None
    for revision in (base, head):
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode:
            return None
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head, "--"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def write_outputs(path: Path, cogs: list[str]) -> None:
    """Write scalar outputs for use by later GitHub Actions jobs."""
    with path.open("a", encoding="utf-8") as output:
        output.write(f"cogs={','.join(cogs)}\n")
        output.write(f"count={len(cogs)}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    available = discover_cogs(root)
    changed = None if args.all else git_changed_files(root, args.base, args.head)
    selected = available if changed is None else select_changed_cogs(changed, available)

    print(f"Selected {len(selected)} cog(s): {', '.join(selected) or 'none'}")
    if args.github_output:
        write_outputs(args.github_output, selected)


if __name__ == "__main__":
    main()
