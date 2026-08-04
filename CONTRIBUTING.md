# Contributing to Taako's Cogs

Thanks for helping improve the repository. Keep pull requests focused, explain the user-visible result, and include tests for new behavior and regressions whenever practical.

## Development setup

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv sync --locked --all-groups
uv run --locked pre-commit run --all-files
uv run --locked python -m pytest -q -p no:cacheprovider
uv run --locked mkdocs build --strict
```

## Cog changes

- Runtime changes must increase the cog's three-part `info.json` version.
- Keep commands, setup, permissions, dependencies, privacy behavior, and examples current in the cog README.
- Declare Python dependencies in the cog's `info.json`, the repository `pyproject.toml`, and its README.
- Add behavior-focused tests, especially for errors, permissions, concurrency, retries, and persistent data.
- Never install packages dynamically from cog code.

## Pull requests

Complete the pull request template. Automated checks validate formatting, metadata, Python compatibility, vulnerable dependency changes, documentation, and live Red loading. Fork and Dependabot pull requests never receive the Discord bot token.

Security vulnerabilities must be reported privately through [GitHub Security Advisories](https://github.com/TaakoOfficial/TaakosCogs/security/advisories/new), not in a public issue.
