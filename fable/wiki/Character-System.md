# 👤 Character System

## Overview

The character system in Fable is designed to bring your roleplay characters to life with rich profiles, development tracking, and interactive features.

## 📝 Character Creation

### Quick Start

```ini
[p]fable character quickstart "Character Name" fantasy
```

Available templates:

- `fantasy` - Fantasy RPG settings
- `modern` - Contemporary settings
- `scifi` - Science Fiction settings
- `supernatural` - Supernatural/Horror settings

### Detailed Creation

```ini
[p]fable character create "Character Name" "Description" --optional-flags
```

Optional Flags:

- `--image_url` - Character portrait
- `--species` - Character race/species
- `--occupation` - Character's role
- `--background` - Character's history
- All other character attributes

## 📊 Character Development

### Milestones

Track character growth with meaningful achievements:

```ini
[p]fable milestone add "Character" "Personal Growth" "Learned to trust again"
[p]fable milestone add "Character" "Achievement" "Became guild master"
```

### Story Arcs

Create and manage character story arcs:

```ini
[p]fable arc create "Arc Title" "Character" "Arc description"
[p]fable arc update "Character" "Arc Title" completed
```

### Timeline View

View a character's journey:

```ini
[p]fable character timeline view "Character"
```

Filter options:

- `--start_date YYYY-MM-DD`
- `--end_date YYYY-MM-DD`
- `--event_type milestone/relationship/story/location`

## 🎭 Character Profiles

### Profile Fields

- **Basic Information**

  - Name
  - Description
  - Image
  - Species/Race
  - Gender
  - Age

- **Background**

  - History
  - Origin
  - Goals
  - Quote

- **Characteristics**
  - Traits
  - Languages
  - Skills
  - Equipment

### Profile Management

```ini
# Edit character details
[p]fable character edit "Character" field "new value"

# View profile
[p]fable character view "Character"

# List all fields
[p]fable character fields
```

## 📈 Development Tracking

### Milestone Categories

- Personal Growth
- Relationship Development
- Story Progress
- Achievement
- Character Development

### Progress Visualization

```ini
# View development chart
[p]fable visualize development "Character"

# Export timeline
[p]fable export timeline "Character"
```

## 🔗 Character Connections

### Relationship Types

- Allies
- Rivals
- Family
- Neutral
- Custom types (configurable)

### Managing Connections

```ini
# Set relationship
[p]fable relationship set "Character1" "Character2" ally 4 "Trust built through adventures"

# View relationships
[p]fable visualize relationships "Character"
```

## 📱 Interactive Features

### Profile Cards

- Customizable themes
- Dynamic relationship displays
- Progress indicators
- Timeline integration

### Development Tools

- Interactive milestone tracking
- Story arc progression
- Relationship graphs
- Location history

## 🎨 Customization

### Profile Themes

```ini
[p]fable character theme set "Character" nature
[p]fable character theme list
```

### Custom Fields

Server admins can add custom fields:

```ini
[p]fable settings addfield "field_name" "Field Description"
```

## 📤 Export Options

### Google Docs

```ini
[p]fable export character "Character" docs
```

### Backup

```ini
[p]fable backup characters
```

## 🔍 Tips & Tricks

1. Use templates for quick character creation
2. Regular milestone updates keep history engaging
3. Link characters to locations for richer storytelling
4. Use relationship intensity for dynamic interactions
5. Export regularly for backup and sharing

## 🤝 Community Templates

Share and use community-made templates:

```ini
[p]fable template share "Template Name"
[p]fable template browse
```

For more examples and community templates, visit our [Template Gallery](Template-Gallery).
