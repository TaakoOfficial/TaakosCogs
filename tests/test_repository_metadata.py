"""Repository-wide metadata, dependency, and workflow policy checks."""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

import tomllib
import yaml

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
        assert data["min_python_version"] >= [3, 10, 0], path
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


def test_cog_readmes_document_declared_requirements() -> None:
    for path in _cog_info_files():
        requirements = json.loads(path.read_text(encoding="utf-8"))["requirements"]
        if not requirements:
            continue
        readme = (path.parent / "README.md").read_text(encoding="utf-8")
        assert "## Requirements" in readme, path
        assert "Downloader" in readme, path
        for requirement in requirements:
            assert requirement.casefold() in readme.casefold(), (path, requirement)


def test_dependabot_covers_every_locked_update_source() -> None:
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    ecosystems = {update["package-ecosystem"] for update in config["updates"]}
    assert ecosystems == {"uv", "github-actions", "pre-commit"}
    assert all(update["directory"] == "/" for update in config["updates"])
    assert all(update["schedule"]["interval"] == "weekly" for update in config["updates"])


def test_documentation_site_is_versioned_and_deployed_from_main() -> None:
    # BaseLoader intentionally leaves Material's !!python/name emoji hooks as strings.
    config = yaml.load(
        (ROOT / "mkdocs.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert config["site_url"] == "https://taakoofficial.github.io/TaakosCogs/latest/"
    assert config["site_dir"] == "site/latest"
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "actions/deploy-pages@" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow


def test_pull_request_automation_covers_repository_policy() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    guardrails = (ROOT / ".github" / "workflows" / "pr-guardrails.yml").read_text(encoding="utf-8")
    compatibility = (ROOT / ".github" / "workflows" / "compatibility.yml").read_text(encoding="utf-8")
    assert "name: Pre-commit" in ci
    assert "pre-commit run --all-files --show-diff-on-failure" in ci
    assert "pull_request:" in guardrails
    assert "pull_request_target" not in guardrails
    assert "name: Dependency Review" in guardrails
    assert "name: Cog Release Policy" in guardrails
    for version in ('"3.10"', '"3.11"'):
        assert version in compatibility
    assert '"3.9"' not in compatibility


def test_labeler_is_privileged_but_never_executes_pull_request_code() -> None:
    workflow = (ROOT / ".github" / "workflows" / "labeler.yml").read_text(encoding="utf-8")
    assert "pull_request_target:" in workflow
    assert "pull-requests: write" in workflow
    assert "actions/checkout@" not in workflow
    assert "run:" not in workflow

    config = yaml.safe_load((ROOT / ".github" / "labeler.yml").read_text(encoding="utf-8"))
    labels = set(config) - {"changed-files-labels-limit", "max-files-changed"}
    expected_cog_labels = {f"cog: {path.parent.name}" for path in _cog_info_files()}
    assert expected_cog_labels <= labels
    assert {"CI", "dependencies", "documentation", "new-cog", "tests"} <= labels


def test_repository_has_structured_contribution_templates() -> None:
    assert (ROOT / ".github" / "pull_request_template.md").is_file()
    assert (ROOT / "CONTRIBUTING.md").is_file()
    assert (ROOT / "SECURITY.md").is_file()
    issue_forms = ROOT / ".github" / "ISSUE_TEMPLATE"
    for name in ("bug.yml", "feature.yml", "config.yml"):
        form = yaml.safe_load((issue_forms / name).read_text(encoding="utf-8"))
        assert form
    assert not list(issue_forms.glob("*.md"))


def test_fable_declares_its_import_time_google_dependencies() -> None:
    data = json.loads((ROOT / "fable" / "info.json").read_text(encoding="utf-8"))
    requirements = {_requirement_name(requirement) for requirement in data["requirements"]}
    assert {"google-api-python-client", "google-auth", "graphviz"} <= requirements


def test_cogs_do_not_install_dependencies_at_runtime() -> None:
    runtime_install_markers = ('"-m", "pip", "install"', "'-m', 'pip', 'install'")
    offenders = [
        path.relative_to(ROOT)
        for info_path in _cog_info_files()
        for path in info_path.parent.glob("*.py")
        if any(marker in path.read_text(encoding="utf-8") for marker in runtime_install_markers)
    ]
    assert not offenders


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
        workflow = path.read_text(encoding="utf-8")
        assert yaml.safe_load(workflow), path
        revisions = ACTION_RE.findall(workflow)
        assert revisions, path
        assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for revision in revisions), path


def test_live_bot_secret_is_gated_to_trusted_repository_code() -> None:
    workflow = (ROOT / ".github" / "workflows" / "live-cog-load.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow
    assert "pull_request_target" not in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "github.actor != 'dependabot[bot]'" in workflow
    assert "github.event_name != 'workflow_dispatch' || github.ref == 'refs/heads/main'" in workflow
    assert "secrets.DISCORD_BOT_TOKEN" in workflow
    assert "COG_PATHS: ${{ needs.changes.outputs.cogs }}" in workflow
