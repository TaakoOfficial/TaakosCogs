# 📈 Timeline & Story Arcs

## Overview

The Timeline system in Fable helps you track character development, story progression, and important events in your roleplay world. Combined with Story Arcs, it creates a rich narrative history for your characters.

## 📅 Timeline Features

### Event Types

- 🎯 **Milestones** - Character achievements and growth
- 👥 **Relationships** - Changes in character connections
- 📖 **Story** - Plot developments and arc progression
- 📍 **Location** - Significant place visits and events
- 📈 **Development** - Personal character growth

### Viewing Timelines

```ini
# View character timeline
[p]fable character timeline view "Character"

# Filter by date range
[p]fable character timeline view "Character" --start_date 2025-01-01 --end_date 2025-04-21

# Filter by event type
[p]fable character timeline view "Character" --event_type milestone
```

## 📚 Story Arcs

### Creating Story Arcs

```ini
# Start a new arc
[p]fable arc create "Arc Title" "Character" "Arc description"

# Add arc milestones
[p]fable arc milestone add "Arc Title" "Character" "Milestone description"

# Update arc status
[p]fable arc update "Character" "Arc Title" completed
```

### Arc Types

- **Personal** - Character development journeys
- **Relationship** - Interpersonal story arcs
- **Quest** - Goal-oriented storylines
- **Background** - Character history elements
- **Group** - Multi-character story arcs

## 🎯 Development Tracking

### Adding Milestones

```ini
# Record character growth
[p]fable milestone add "Character" "Personal Growth" "Overcame their greatest fear"

# Add with details
[p]fable milestone add "Character" "Achievement" "Became guild master" --date "2025-04-21" --location "Guild Hall"
```

### Categories

- Personal Growth
- Relationship Development
- Story Progress
- Achievement
- Character Development

## 📊 Visualization

### Timeline Views

```ini
# Visual timeline
[p]fable visualize timeline "Character"

# Development chart
[p]fable visualize development "Character"

# Story arc progression
[p]fable visualize arc "Arc Title"
```

### Interactive Features

- Click events for details
- Filter by type or date
- Zoom in/out on timeline
- Export as image

## 🔄 Story Progression

### Tracking Progress

```ini
# Update arc progress
[p]fable arc progress "Arc Title" 75 "Nearing the climax"

# Add arc events
[p]fable arc event add "Arc Title" "A crucial revelation"
```

### Arc Connections

```ini
# Link characters to arc
[p]fable arc character add "Arc Title" "Character" "Supporting Role"

# Connect locations
[p]fable arc location add "Arc Title" "Location" "Scene of the climax"
```

## 📱 Interactive Features

### Timeline Navigation

- Forward/backward in time
- Jump to significant events
- Filter view options
- Search functionality

### Story Management

- Arc branching
- Character involvement tracking
- Location integration
- Relationship impact

## 📤 Export Options

### Documentation

```ini
# Export timeline
[p]fable export timeline "Character" docs

# Export story arc
[p]fable export arc "Arc Title" docs
```

### Visual Exports

```ini
# Save timeline visualization
[p]fable visualize timeline "Character" --save

# Export development chart
[p]fable visualize development "Character" --save
```

## 🎨 Customization

### Timeline Display

```ini
# Set timeline theme
[p]fable timeline theme set "Character" classic

# Customize event icons
[p]fable timeline icons customize
```

### Arc Visualization

```ini
# Modify arc display
[p]fable arc display set "Arc Title" branching

# Set custom colors
[p]fable arc color set "Arc Title" #7289DA
```

## 💡 Tips & Best Practices

### Recording Events

1. Be consistent with milestone recording
2. Include relevant context
3. Link to locations and characters
4. Add meaningful descriptions

### Story Arc Management

1. Plan major plot points
2. Track character involvement
3. Update progress regularly
4. Connect related arcs

### Timeline Organization

1. Use clear event titles
2. Categorize properly
3. Include location context
4. Note relationship impacts

## 🔍 Search & Analysis

### Finding Events

```ini
# Search timeline
[p]fable timeline search "Character" "keyword"

# Find related events
[p]fable timeline related "Event ID"
```

### Analytics

```ini
# Character development analysis
[p]fable analyze development "Character"

# Arc progression stats
[p]fable analyze arc "Arc Title"
```

## 🤝 Collaborative Features

### Multi-Character Arcs

```ini
# Create group arc
[p]fable arc group create "Arc Title" "Description"

# Add characters
[p]fable arc group add "Arc Title" "Character1" "Character2"
```

### Shared Timelines

```ini
# View group timeline
[p]fable timeline view --group "Guild Name"

# Export group history
[p]fable export timeline --group "Guild Name"
```

---

For more examples and story templates, visit our [Story Arc Gallery](Story-Arc-Gallery).
