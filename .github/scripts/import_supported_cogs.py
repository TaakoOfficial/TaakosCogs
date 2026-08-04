"""Import every cog that declares support for the running Python version."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def supported_cogs(root: Path, version: tuple[int, int, int]) -> list[str]:
    """Return cogs whose declared minimum Python version is satisfied."""
    cogs: list[str] = []
    for info_path in root.glob("*/info.json"):
        if not (info_path.parent / "__init__.py").is_file():
            continue
        metadata = json.loads(info_path.read_text(encoding="utf-8"))
        minimum = tuple(int(part) for part in metadata["min_python_version"])
        if minimum <= version:
            cogs.append(info_path.parent.name)
    return sorted(cogs)


def declared_requirements(root: Path) -> list[str]:
    """Return de-duplicated requirement strings declared by installable cogs."""
    requirements = {
        requirement
        for info_path in root.glob("*/info.json")
        if (info_path.parent / "__init__.py").is_file()
        for requirement in json.loads(info_path.read_text(encoding="utf-8")).get("requirements", [])
    }
    return sorted(requirements, key=str.casefold)


def import_cogs(root: Path) -> list[tuple[str, BaseException]]:
    """Import supported cogs and return every failure instead of stopping early."""
    sys.path.insert(0, str(root))
    version = sys.version_info[:3]
    failures: list[tuple[str, BaseException]] = []
    cogs = supported_cogs(root, version)
    for cog in cogs:
        try:
            importlib.import_module(cog)
        except BaseException as error:  # noqa: BLE001 - report all import-time failures together
            failures.append((cog, error))
    print(f"Imported {len(cogs) - len(failures)}/{len(cogs)} supported cogs on Python {version[0]}.{version[1]}.")
    return failures


def main() -> None:
    if "--requirements" in sys.argv:
        print("Red-DiscordBot>=3.5.0,<3.6")
        # Red runs inside a normal virtual environment where pip is present;
        # uv-created compatibility environments are intentionally seedless.
        print("pip>=23.3,<26")
        print("\n".join(declared_requirements(ROOT)))
        return

    failures = import_cogs(ROOT)
    for cog, error in failures:
        print(f"{cog}: {type(error).__name__}: {error}", file=sys.stderr)
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
