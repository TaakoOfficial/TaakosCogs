"""Tests for pull-request cog release metadata policy."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "cog_policy.py"
SPEC = importlib.util.spec_from_file_location("cog_policy", SCRIPT)
assert SPEC and SPEC.loader
cog_policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = cog_policy
SPEC.loader.exec_module(cog_policy)


def make_cog(root: Path, name: str, version: str = "1.0.0") -> None:
    directory = root / name
    directory.mkdir()
    (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / "cog.py").write_text("VALUE = 1\n", encoding="utf-8")
    (directory / "README.md").write_text(f"# {name}\n", encoding="utf-8")
    (directory / "info.json").write_text(json.dumps({"version": version}), encoding="utf-8")


def test_runtime_change_requires_version_bump(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha")
    violations = cog_policy.validate_changes(
        tmp_path,
        ["alpha/cog.py"],
        {"alpha": {"version": "1.0.0"}},
    )
    assert violations == ["alpha: runtime files changed without bumping info.json version above 1.0.0"]


def test_runtime_change_accepts_version_bump(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha", "1.0.1")
    assert not cog_policy.validate_changes(
        tmp_path,
        ["alpha/cog.py", "alpha/info.json"],
        {"alpha": {"version": "1.0.0"}},
    )


def test_documentation_change_does_not_require_version_bump(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha")
    assert not cog_policy.validate_changes(
        tmp_path,
        ["alpha/README.md", "alpha/CHANGELOG.md", "alpha/wiki/custom.css"],
        {"alpha": {"version": "1.0.0"}},
    )


def test_version_cannot_decrease(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha", "1.9.0")
    violations = cog_policy.validate_changes(
        tmp_path,
        ["alpha/info.json"],
        {"alpha": {"version": "2.0.0"}},
    )
    assert violations == ["alpha: version decreased from 2.0.0 to 1.9.0"]


def test_new_cog_requires_readme(tmp_path: Path) -> None:
    make_cog(tmp_path, "alpha")
    (tmp_path / "alpha" / "README.md").unlink()
    assert cog_policy.validate_changes(tmp_path, ["alpha/cog.py"], {"alpha": None}) == [
        "alpha: new cogs require a README.md",
    ]
