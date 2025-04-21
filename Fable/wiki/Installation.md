# 📥 Installation Guide

## Prerequisites

- Red-DiscordBot V3.5.0+
- Python 3.10+
- Discord Bot with Server Management permissions

## Step-by-Step Installation

### 1️⃣ Add the Repository

```ini
[p]repo add taako https://github.com/TaakoOfficial/TaakosCogs
```

### 2️⃣ Install the Cog

```ini
[p]cog install TaakosCogs Fable
```

### 3️⃣ Load the Cog

```ini
[p]load Fable
```

## Initial Setup

### 1️⃣ Run the Setup Wizard

```ini
[p]fable setup
```

This will guide you through:

- Setting up character templates
- Configuring relationship types
- Setting up location categories
- Customizing milestone tracking

### 2️⃣ Configure Optional Features

#### Google Integration

For backup and export features:

1. Create a Google Cloud project
2. Enable the Google Drive and Sheets APIs
3. Create service account credentials
4. See [Google Integration](Google-Integration) for detailed steps

#### Visualization Features

The cog will automatically install required packages:

- `graphviz` for relationship and location graphs
- Additional Python dependencies

## Permissions

Fable uses the following Discord permissions:

- `Send Messages`
- `Embed Links`
- `Attach Files`
- `Add Reactions`
- `Use External Emojis`
- `Manage Messages` (for interactive features)

## Command Access Levels

- **Admin Commands**

  - Server setup
  - Template management
  - Category configuration
  - Backup management

- **Moderator Commands**

  - Character approval
  - Event moderation
  - Location management

- **User Commands**
  - Character creation/editing
  - Relationship management
  - Timeline viewing
  - Location visiting

## Troubleshooting

Having issues? Check our common solutions:

### Package Installation Failed

```ini
[p]reload Fable
```

This will trigger automatic package installation again.

### Visualization Not Working

1. Ensure Graphviz is installed:

```bash
[p]fable doctor
```

2. Check the error log:

```ini
[p]fable debug
```

For more issues, see our [Troubleshooting Guide](Troubleshooting).
