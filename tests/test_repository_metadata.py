"""Repository-wide metadata, dependency, and workflow policy checks."""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
ACTION_RE = re.compile(r"\buses:\s*[^\s@]+@([^\s#]+)")


def _cog_info_files() -> list[Path]:
    return sorted(path for path in ROOT.glob("*/info.json") if (path.parent / "__init__.py").is_file())


def _requirement_name(requirement: str) -> str:
    name = re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def _dotted_name(node: ast.expr) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _app_group_name(class_node: ast.ClassDef) -> str | None:
    if not any(_dotted_name(base) == "app_commands.Group" for base in class_node.bases):
        return None
    initializer = next(
        (
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__init__"
        ),
        None,
    )
    if initializer is None:
        return None
    for node in ast.walk(initializer):
        is_super_init = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "__init__"
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "super"
        )
        if is_super_init:
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    return str(keyword.value.value).casefold()
    return None


def test_repository_and_cog_metadata_are_complete() -> None:
    repository = json.loads((ROOT / "info.json").read_text(encoding="utf-8"))
    assert repository["type"] == "REPO"
    assert repository["name"]
    assert repository["author"]
    assert repository["description"]

    cogs = _cog_info_files()
    assert len(cogs) >= 38
    for path in cogs:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"].casefold() == path.parent.name.casefold(), path
        assert data["type"] == "COG", path
        assert VERSION_RE.fullmatch(data["version"]), path
        assert VERSION_RE.fullmatch(data["min_bot_version"]), path
        assert len(data["min_python_version"]) == 3, path
        assert all(isinstance(part, int) for part in data["min_python_version"]), path
        assert isinstance(data["requirements"], list), path
        assert all(isinstance(requirement, str) and requirement for requirement in data["requirements"]), path
        assert data["end_user_data_statement"].strip(), path


def test_locked_environment_covers_every_cog_requirement() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    root_requirements = {_requirement_name(item) for item in project["project"]["dependencies"]}
    cog_requirements = {
        _requirement_name(requirement)
        for path in _cog_info_files()
        for requirement in json.loads(path.read_text(encoding="utf-8"))["requirements"]
    }
    assert cog_requirements <= root_requirements


def test_root_command_names_do_not_overlap_between_cogs() -> None:
    command_decorators = {
        "commands.command",
        "commands.group",
        "commands.hybrid_command",
        "commands.hybrid_group",
        "app_commands.command",
    }
    registrations: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for path in sorted(ROOT.glob("*/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            app_group = _app_group_name(class_node)
            methods = (node for node in class_node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            for method in methods:
                for decorator in method.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    decorator_name = _dotted_name(decorator.func)
                    if decorator_name not in command_decorators:
                        continue
                    command_name = method.name
                    aliases: list[str] = []
                    for keyword in decorator.keywords:
                        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                            command_name = str(keyword.value.value)
                        elif keyword.arg == "aliases" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                            aliases = [str(item.value) for item in keyword.value.elts if isinstance(item, ast.Constant)]
                    location = f"{path.relative_to(ROOT)}:{method.lineno}"
                    if decorator_name.startswith("commands."):
                        for name in (command_name, *aliases):
                            registrations[("prefix", name.casefold())].append(location)
                    if decorator_name.startswith("commands.hybrid_"):
                        registrations[("slash", command_name.casefold())].append(location)
                    elif decorator_name == "app_commands.command":
                        qualified_name = f"{app_group} {command_name}" if app_group else command_name
                        registrations[("slash", qualified_name.casefold())].append(location)

    collisions = {name: locations for name, locations in registrations.items() if len(locations) > 1}
    assert not collisions


def test_workflow_actions_are_commit_pinned() -> None:
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows
    for path in workflows:
        revisions = ACTION_RE.findall(path.read_text(encoding="utf-8"))
        assert revisions, path
        assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in revisions), path


def test_live_bot_secret_is_manual_and_main_branch_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "live-cog-load.yml").read_text(encoding="utf-8")
    assert "pull_request" not in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "secrets.DISCORD_BOT_TOKEN" in workflow
