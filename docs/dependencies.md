# Dependencies

## Python packages

Each cog declares external Python packages in its `info.json`. Red's Downloader installs those requirements automatically during `[p]cog install`; users should not run `pip install` inside a cog or modify Red's environment manually.

The repository's `pyproject.toml` and `uv.lock` provide a reproducible Python 3.11 environment for CI and development. Automated tests ensure every cog requirement is represented in that lock environment and documented in the cog README.

## Host-level requirements

Most cogs need no host packages beyond a supported Red installation. The notable exception is Fable's relationship and location graph rendering:

```bash
sudo apt install graphviz
```

The Python `graphviz` package is installed by Downloader, but the host must provide the `dot` executable used to render PNG files.

## External services

Features that connect to external systems remain opt-in:

- Fable Google Docs and Sheets sync requires a Google service account and enabled APIs.
- WHMCS commands require an HTTPS-accessible WHMCS API installation.
- FiveM and link-monitoring features require outbound access to their configured endpoints.

Credentials should be entered only through the private slash-command or dashboard paths documented by each cog.

## Updates

Dependabot checks `uv.lock`, GitHub Actions, and pre-commit hooks weekly. Dependency pull requests run tokenless CI; merged lockfile changes trigger the complete live cog-load suite on `main`.
