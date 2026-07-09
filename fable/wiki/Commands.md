# 📜 Command Reference

A complete guide to all Fable commands, organized by feature category.

## Character Commands

### Basic Character Management

```ini
# Create character
[p]fable character create "Name" "Description"
[p]fable character quickstart "Name" template_name

# View & Edit
[p]fable character view "Name"
[p]fable character edit "Name" field "value"
[p]fable character delete "Name"
```

### Character Development

```ini
# Milestones
[p]fable milestone add "Character" category "Description"
[p]fable milestone list "Character"
[p]fable milestone categories

# Story Arcs
[p]fable arc create "Title" "Character" "Description"
[p]fable arc update "Character" "Title" status
[p]fable arc list "Character"
```

### Timeline & History

```ini
[p]fable character timeline view "Character"
[p]fable character history "Character"
[p]fable character events "Character"
```

## Relationship Commands

### Managing Relationships

```ini
# Set & Update
[p]fable relationship set "Char1" "Char2" type intensity "Description"
[p]fable relationship update "Char1" "Char2" intensity "Note"

# Viewing
[p]fable relationship view "Char1" "Char2"
[p]fable relationship list "Character"
```

### Family Connections

```ini
[p]fable family add "Parent" "Child" parent
[p]fable family add "Char1" "Char2" sibling
[p]fable family tree "Character"
```

## Location Commands

### Location Management

```ini
# Basic Management
[p]fable location create "Name" category "Description"
[p]fable location edit "Name" field "value"
[p]fable location delete "Name"

# Connections
[p]fable location connect "Location1" "Location2" "Description"
[p]fable location disconnect "Location1" "Location2"
```

### Visit Tracking

```ini
[p]fable location visit "Location" "Character" "Note"
[p]fable location history "Location"
[p]fable location visitors "Location"
```

## Visualization Commands

### Relationship Graphs

```ini
[p]fable visualize relationships "Character"
[p]fable visualize relationships --all
[p]fable visualize relationships --group "Group"
```

### Location Maps

```ini
[p]fable visualize locations
[p]fable visualize locations --region "Region"
[p]fable visualize locations --connected "Location"
```

### Timelines

```ini
[p]fable visualize timeline "Character"
[p]fable visualize development "Character"
[p]fable visualize arc "Arc Title"
```

## Export & Backup Commands

### Google Integration

```ini
# Setup
[p]fable google setup
[p]fable google test
[p]fable google disconnect

# Export
[p]fable export character "Character" docs
[p]fable export timeline "Character" docs
[p]fable export relationships docs
```

### Local Backup

```ini
[p]fable backup all
[p]fable backup characters
[p]fable backup locations
[p]fable restore backup_name
```

## Administrative Commands

### Server Settings

```ini
# General Settings
[p]fable settings view
[p]fable settings edit setting_name value
[p]fable settings reset

# Permissions
[p]fable settings permissions role_name permission_level
```

### Template Management

```ini
[p]fable template list
[p]fable template create "Name"
[p]fable template edit "Name"
[p]fable template delete "Name"
```

## Utility Commands

### System Management

```ini
# Maintenance
[p]fable cache clear
[p]fable index rebuild
[p]fable optimize

# Diagnostics
[p]fable doctor
[p]fable debug info
[p]fable logs show
```

### Help & Information

```ini
[p]help fable
[p]fable about
[p]fable version
```

## Advanced Features

### Custom Fields

```ini
[p]fable settings addfield "field_name" "Description"
[p]fable settings removefield "field_name"
```

### Event Scheduling

```ini
[p]fable event schedule "Location" "Title" "2025-05-01 20:00"
[p]fable event recurring "Location" "Title" "Every Saturday"
```

### Data Analysis

```ini
[p]fable analyze relationships "Character"
[p]fable analyze locations "Area"
[p]fable analyze development "Character"
```

## Command Parameters

### Common Parameters

- `--quiet`: Suppress confirmation messages
- `--force`: Override warnings
- `--yes`: Auto-confirm actions
- `--save`: Export to file
- `--format`: Specify output format

### Time Parameters

- `--start_date`: Starting date (YYYY-MM-DD)
- `--end_date`: Ending date (YYYY-MM-DD)
- `--timezone`: Specify timezone

### Filter Parameters

- `--type`: Filter by type
- `--category`: Filter by category
- `--intensity`: Filter by relationship intensity
- `--region`: Filter by region

## Command Cooldowns

Most commands have a 5-second cooldown per user, with exceptions:

- Visualization commands: 30 seconds
- Backup commands: 1 hour
- Template creation: 1 minute

## Permission Levels

### User Commands

Available to all users:

- Character viewing
- Basic relationship management
- Location visits
- Timeline viewing

### Moderator Commands

Requires manage_messages:

- Character approval
- Event moderation
- Location management
- Template creation

### Admin Commands

Requires administrator:

- Server settings
- Template management
- Backup control
- Permission management

---

For more detailed information about specific commands, use:

```ini
[p]help fable command_name
```
