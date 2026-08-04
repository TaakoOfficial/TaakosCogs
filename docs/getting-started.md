# Getting started

## Add the repository

Run these commands in Discord using your Red bot prefix:

```text
[p]load downloader
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]repo update
```

## Install a cog

```text
[p]cog install taakoscogs <cogname>
[p]load <cogname>
```

For example:

```text
[p]cog install taakoscogs yalc
[p]load yalc
```

Red's Downloader reads the selected cog's `info.json`, installs its declared Python dependencies, and copies the cog into Red's managed install path.

## Update installed cogs

```text
[p]cog update
```

Review release notes before updating heavily configured production cogs, then reload when Red requests it.

## Find commands

```text
[p]help <cogname>
```

Many cogs provide hybrid prefix and slash commands. Configurable cogs also include focused Red-Web-Dashboard pages when the dashboard integration is installed and enabled.

## Permissions

Each cog reference lists its Discord and host requirements. Grant only the permissions needed for enabled features, and keep the bot's managed role above any roles it must assign.
