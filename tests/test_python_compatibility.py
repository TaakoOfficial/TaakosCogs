"""Tests for Python-version-aware cog import selection."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "import_supported_cogs.py"
SPEC = importlib.util.spec_from_file_location("import_supported_cogs", SCRIPT)
assert SPEC and SPEC.loader
compatibility = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compatibility)


def make_cog(root: Path, name: str, minimum: tuple[int, int, int], requirements: list[str]) -> None:
    directory = root / name
    directory.mkdir()
    (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / "info.json").write_text(
        json.dumps({"min_python_version": minimum, "requirements": requirements}),
        encoding="utf-8",
    )


def test_selects_only_cogs_supported_by_interpreter(tmp_path: Path) -> None:
    make_cog(tmp_path, "legacy", (3, 9, 0), [])
    make_cog(tmp_path, "modern", (3, 11, 0), [])
    assert compatibility.supported_cogs(tmp_path, (3, 10, 9)) == ["legacy"]


def test_collects_unique_declared_requirements(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha", (3, 9, 0), ["aiohttp", "PyYAML>=6"])
    make_cog(tmp_path, "beta", (3, 10, 0), ["aiohttp"])
    assert compatibility.declared_requirements(tmp_path) == ["aiohttp", "PyYAML>=6"]
