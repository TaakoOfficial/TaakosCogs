"""Tests for changed-cog selection used by Live Cog Load."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "changed_cogs.py"
SPEC = importlib.util.spec_from_file_location("changed_cogs", SCRIPT)
assert SPEC and SPEC.loader
changed_cogs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changed_cogs)


def test_discovers_only_installable_cog_directories(tmp_path: Path) -> None:
    for name in ("alpha", "beta"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "info.json").write_text("{}", encoding="utf-8")
        (directory / "__init__.py").write_text("", encoding="utf-8")
    incomplete = tmp_path / "not_a_cog"
    incomplete.mkdir()
    (incomplete / "info.json").write_text("{}", encoding="utf-8")

    assert changed_cogs.discover_cogs(tmp_path) == ["alpha", "beta"]


def test_selects_only_cogs_containing_changed_files() -> None:
    selected = changed_cogs.select_changed_cogs(
        ["alpha/alpha.py", "alpha/docs/guide.md", "README.md", "tests/test_alpha.py"],
        ["alpha", "beta"],
    )
    assert selected == ["alpha"]


def test_shared_environment_changes_select_every_cog() -> None:
    assert changed_cogs.select_changed_cogs(["uv.lock"], ["alpha", "beta"]) == ["alpha", "beta"]


def test_unrelated_changes_select_no_live_cogs() -> None:
    assert changed_cogs.select_changed_cogs(["README.md", "tests/test_docs.py"], ["alpha", "beta"]) == []
