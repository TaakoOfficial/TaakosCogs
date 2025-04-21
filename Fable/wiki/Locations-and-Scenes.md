# 🗺️ Locations & Scenes

## Overview

The Locations system helps you build a rich, interconnected world for your roleplay. Create detailed locations, track character visits, and visualize how different areas connect to each other.

## 🏰 Location Types

### Built-in Categories

- `tavern` - Inns, bars, and gathering places (Brown)
- `castle` - Castles, keeps, and fortresses (Gray)
- `house` - Homes, apartments, and residential areas (Green)
- `shop` - Stores, markets, and trading posts (Yellow)
- `dungeon` - Dungeons, caves, and dangerous areas (Dark Red)
- `custom` - Custom location types (Light Blue)

## 📝 Creating Locations

### Basic Creation

```ini
[p]fable location create "Location Name" category "Description"
```

Example:

```ini
[p]fable location create "The Rusty Dragon" tavern "A cozy tavern known for its spicy ale and friendly atmosphere"
```

### Advanced Options

```ini
[p]fable location create "Crystal Cave" dungeon "An ancient cave filled with glowing crystals" --region "Northern Mountains" --danger_level 3 --owner "Mysterious Hermit"
```

## 🔗 Connecting Locations

### Creating Connections

```ini
[p]fable location connect "Starting Location" "Destination" "Description of the connection"
```

Example:

```ini
[p]fable location connect "Marketplace" "Thieves' Guild" "Hidden entrance through a secret door in the well"
```

### Types of Connections

- Physical paths
- Secret passages
- Magical portals
- Trade routes
- Political connections

## 👣 Character Visits

### Recording Visits

```ini
[p]fable location visit "Location" "Character" "Optional note about the visit"
```

### Viewing History

```ini
[p]fable location history "Location"
[p]fable character visits "Character"
```

## 🎭 Scenes & Events

### Creating Scenes

```ini
[p]fable scene create "Location" "Scene Title" "Description" @Character1 @Character2
```

### Scene Management

```ini
[p]fable scene start "Scene ID"
[p]fable scene end "Scene ID" "Summary of what happened"
```

## 🗺️ Visualization

### Location Maps

```ini
[p]fable visualize locations
[p]fable visualize locations --region "Northern Mountains"
```

Features:

- Color-coded by location type
- Connection lines showing paths
- Icons for special features
- Interactive node exploration

### Custom Icons

Admins can set custom icons:

```ini
[p]fable location icon set "Location" 🏰
```

## 📊 Location Analytics

### Traffic Analysis

```ini
[p]fable location stats "Location"
```

Shows:

- Most frequent visitors
- Peak activity times
- Popular connections
- Event frequency

### Character Patterns

```ini
[p]fable location patterns "Character"
```

Reveals:

- Favorite locations
- Travel patterns
- Regular haunts
- Avoided areas

## 🏷️ Location Features

### Adding Features

```ini
[p]fable location feature add "Location" "Feature Name" "Description"
```

Example Features:

- Special items
- NPCs
- Services
- Hazards
- Points of interest

### Managing Access

```ini
[p]fable location access set "Location" restricted "Only guild members allowed"
```

## 📅 Events & Scheduling

### Scheduling Events

```ini
[p]fable event schedule "Location" "Event Title" "2025-05-01 20:00 UTC"
```

### Regular Events

```ini
[p]fable event recurring "Location" "Weekly Market" "Every Saturday"
```

## 🔍 Search & Discovery

### Finding Locations

```ini
[p]fable location search "query"
[p]fable location nearby "Current Location"
```

### Filtering Options

```ini
[p]fable location list --type tavern --region "Capital City"
```

## 📝 Location Templates

### Using Templates

```ini
[p]fable location template use "tavern" "New Tavern Name"
```

### Creating Templates

```ini
[p]fable location template save "Current Location" "Template Name"
```

## 🔐 Management Commands

### Admin Controls

```ini
[p]fable location rename "Old Name" "New Name"
[p]fable location archive "Location"
[p]fable location merge "Location1" "Location2"
```

## 📤 Export Options

### Documentation

```ini
[p]fable export locations docs
```

### Maps

```ini
[p]fable visualize locations --save "world_map.png"
```

## 💡 Tips & Best Practices

1. **Rich Descriptions**

   - Include atmospheric details
   - Note important features
   - Mention historical significance

2. **Meaningful Connections**

   - Create logical pathways
   - Include travel methods
   - Note connection conditions

3. **Regular Updates**

   - Keep visit logs current
   - Update features as they change
   - Archive unused locations

4. **Organization**
   - Use consistent naming
   - Group by regions
   - Maintain clear hierarchies

---

For community-created location templates and ideas, visit our [Location Gallery](Location-Gallery).
