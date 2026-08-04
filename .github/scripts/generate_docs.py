"""Generate MkDocs cog reference pages from canonical repository READMEs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

import mkdocs_gen_files

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_BLOB = "https://github.com/TaakoOfficial/TaakosCogs/blob/main"
REPOSITORY_RAW = "https://raw.githubusercontent.com/TaakoOfficial/TaakosCogs/main"
RELATIVE_LINK_RE = re.compile(
    r"(?P<image>!)?\[(?P<label>[^]]*)\]\((?P<target>\.{1,2}/[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)",
)


def repository_link(source: Path, target: str, *, image: bool) -> str:
    """Convert one README-relative target to an immutable repository URL shape."""
    path_text, separator, fragment = target.partition("#")
    resolved = (source.parent / path_text).resolve().relative_to(ROOT)
    base = REPOSITORY_RAW if image else REPOSITORY_BLOB
    url = f"{base}/{quote(resolved.as_posix(), safe='/')}"
    return f"{url}#{fragment}" if separator else url


def normalize_readme_links(source: Path, markdown: str) -> str:
    """Keep copied README links valid from generated documentation paths."""

    def replace(match: re.Match[str]) -> str:
        image = bool(match.group("image"))
        prefix = "!" if image else ""
        target = repository_link(source, match.group("target"), image=image)
        title = match.group("title") or ""
        return f"{prefix}[{match.group('label')}]({target}{title})"

    return RELATIVE_LINK_RE.sub(replace, markdown)


def cog_records() -> list[tuple[str, str, Path]]:
    """Return display name, directory, and README for every installable cog."""
    records: list[tuple[str, str, Path]] = []
    for info_path in ROOT.glob("*/info.json"):
        if not (info_path.parent / "__init__.py").is_file():
            continue
        data = json.loads(info_path.read_text(encoding="utf-8"))
        records.append((str(data["name"]), info_path.parent.name, info_path.parent / "README.md"))
    return sorted(records, key=lambda record: record[0].casefold())


nav = mkdocs_gen_files.Nav()
nav["Home"] = "index.md"
nav["Getting Started"] = "getting-started.md"
nav["Dependencies"] = "dependencies.md"
nav["Contributing"] = "contributing.md"

for display_name, directory, readme_path in cog_records():
    generated_path = Path("cogs") / f"{directory}.md"
    markdown = normalize_readme_links(readme_path, readme_path.read_text(encoding="utf-8"))
    with mkdocs_gen_files.open(generated_path, "w") as generated:
        generated.write(markdown)
    nav["Cog Reference", display_name] = generated_path.as_posix()

with mkdocs_gen_files.open("SUMMARY.md", "w") as summary:
    summary.writelines(nav.build_literate_nav())
