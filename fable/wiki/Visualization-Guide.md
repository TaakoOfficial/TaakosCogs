# 📊 Visualization Guide

## Overview

Fable offers powerful visualization tools to help you understand relationships, track character development, and map your world. This guide covers all visual features and how to use them effectively.

## 🎨 Available Visualizations

### 👥 Relationship Graphs

![Relationship Graph Example](../assets/relationship-graph.png)

Color-coded connections show relationship types:

- 💚 Green - Allies
- ❤️ Red - Rivals
- 💙 Blue - Family
- ⚪ Gray - Neutral
- 🟣 Purple - Custom types

```ini
# Generate relationship graph
[p]fable visualize relationships "Character"

# Full network view
[p]fable visualize relationships --all

# Export as image
[p]fable visualize relationships --save
```

### 🗺️ Location Maps

![Location Map Example](../assets/location-map.png)

Location types use distinct colors:

- 🟫 Brown - Taverns/Inns
- ⬜ Gray - Castles/Fortresses
- 🟩 Green - Houses/Residences
- 🟨 Yellow - Shops/Markets
- 🟥 Dark Red - Dungeons
- 🟦 Light Blue - Other

```ini
# Generate world map
[p]fable visualize locations

# Region-specific map
[p]fable visualize locations --region "Northern Mountains"
```

### 📈 Character Timelines

![Timeline Example](../assets/timeline.png)

Event types with distinct icons:

- 🎯 Milestones
- 👥 Relationships
- 📖 Story Events
- 📍 Location Visits
- 📈 Development

```ini
# View interactive timeline
[p]fable character timeline view "Character"

# Export as image
[p]fable visualize timeline "Character" --save
```

## 🛠️ Customization Options

### Theme Settings

```ini
# Set graph theme
[p]fable visualize theme set modern

# Available themes:
- modern (default)
- classic
- fantasy
- minimalist
- dark
```

### Color Schemes

```ini
# Custom relationship colors
[p]fable visualize colors relationships custom

# Custom location colors
[p]fable visualize colors locations custom
```

### Icon Customization

```ini
# Set custom icons
[p]fable visualize icons set milestone 🌟
```

## 🖼️ Export Options

### Image Formats

- PNG (default) - Best for Discord
- SVG - Scalable graphics
- PDF - Print quality
- GIF - Animated timelines

```ini
# Export with format
[p]fable visualize relationships --format svg
```

### Resolution Settings

```ini
# High-resolution export
[p]fable visualize locations --quality high
```

## 📱 Interactive Features

### Graph Navigation

- 🔍 Zoom in/out
- 🖱️ Click nodes for details
- 🔄 Drag to reorganize
- ⚡ Quick filters

### Timeline Interaction

- ⏮️ Skip to start
- ⏭️ Skip to end
- ⏪ Previous event
- ⏩ Next event
- 🔎 Search events

### Location Map Features

- 🏃‍♂️ Path tracing
- 📍 Location markers
- 🔍 Area zoom
- 📝 Add notes

## 💡 Best Practices

### Graph Clarity

1. Limit visible connections
2. Group related nodes
3. Use meaningful colors
4. Add descriptive labels

### Timeline Organization

1. Regular updates
2. Clear event titles
3. Consistent categorization
4. Meaningful milestones

### Map Management

1. Logical connections
2. Clear area divisions
3. Proper scaling
4. Regular cleanup

## 🔧 Troubleshooting

### Common Issues

- Graph too cluttered
- Timeline not updating
- Export failing
- Layout problems

### Quick Fixes

```ini
# Refresh visualization
[p]fable visualize refresh

# Clear cache
[p]fable visualize cache clear

# Reset settings
[p]fable visualize settings reset
```

## 📊 Advanced Features

### Data Analysis

```ini
# Character network analysis
[p]fable analyze relationships "Character"

# Location traffic patterns
[p]fable analyze locations "Area"

# Timeline statistics
[p]fable analyze timeline "Character"
```

### Custom Layouts

```ini
# Set layout algorithm
[p]fable visualize layout set force

# Available layouts:
- force (default)
- circular
- hierarchical
- grid
- custom
```

### Animation Options

```ini
# Enable timeline animation
[p]fable visualize timeline animate

# Set transition speed
[p]fable visualize speed set normal
```

## 🎓 Tips for Success

1. **Regular Updates**

   - Keep visualizations current
   - Update after major events
   - Regular cleanup of old data

2. **Clear Organization**

   - Use consistent naming
   - Group related elements
   - Maintain hierarchy

3. **Performance**

   - Limit visible elements
   - Use appropriate quality settings
   - Regular cache clearing

4. **Backup**
   - Export important visualizations
   - Save custom settings
   - Document configurations

---

Need more help? Check our [FAQ](FAQ) or join our [Discord Support Server](https://discord.gg/example).
