# 👥 Relationship System

## Overview

The Fable relationship system creates dynamic connections between characters with intensity tracking, history, and beautiful visualizations. Track everything from family ties to rivalries with rich, interactive features.

## 🤝 Core Features

### Relationship Types

- **Allies** (Green connections) - Friendly and cooperative relationships
- **Rivals** (Red connections) - Competitive or antagonistic relationships
- **Family** (Blue connections) - Blood relations and adoptive ties
- **Neutral** (Gray connections) - Acquaintances and known contacts
- **Custom Types** - Server-specific relationship categories

### Intensity Levels

```ini
1 ⭐ - Acquaintance/Distant
2 ⭐⭐ - Familiar/Developing
3 ⭐⭐⭐ - Established/Strong
4 ⭐⭐⭐⭐ - Deep/Intense
5 ⭐⭐⭐⭐⭐ - Unbreakable/Legendary
```

## 📝 Managing Relationships

### Setting Relationships

```ini
# Basic relationship
[p]fable relationship set "Character1" "Character2" ally

# With intensity and description
[p]fable relationship set "Character1" "Character2" rival 4 "Bitter enemies since the artifact theft"

# Family connections
[p]fable relationship set "Character1" "Character2" family 5 "Twin siblings"
```

### Viewing Relationships

```ini
# View single relationship
[p]fable relationship view "Character1" "Character2"

# View all character relationships
[p]fable relationship list "Character1"

# Generate relationship graph
[p]fable visualize relationships "Character1"
```

## 📈 Relationship Development

### Historical Tracking

The system automatically maintains relationship history:

- Previous relationship states
- When changes occurred
- Who made the changes
- Notes and context

View history with:

```ini
[p]fable relationship history "Character1" "Character2"
```

### Relationship Events

Log significant moments:

```ini
[p]fable relationship event "Character1" "Character2" "Fought side by side against the dragon"
```

## 🗺️ Visualization Features

### Network Graphs

Generate visual relationship maps:

```ini
# For one character
[p]fable visualize relationships "Character1"

# For a group
[p]fable visualize relationships --group "Guild Name"

# Full server map
[p]fable visualize relationships --all
```

### Interactive Features

- Click nodes to view character details
- Hover for relationship descriptions
- Filter by relationship type
- Adjust visualization layout
- Export as image

## 👨‍👩‍👧‍👦 Family Trees

### Creating Family Connections

```ini
[p]fable family add "Parent" "Child" parent
[p]fable family add "Character1" "Character2" sibling
```

### Viewing Family Trees

```ini
[p]fable family tree "Character"
[p]fable family list "Character"
```

## 🔄 Relationship Development

### Progressive Development

Track how relationships evolve:

```ini
[p]fable relationship progress "Character1" "Character2"
```

### Milestone Integration

```ini
[p]fable milestone add "Character" relationship "Became blood brothers with Char2"
```

## ⚙️ Configuration

### Custom Relationship Types

Admins can create server-specific types:

```ini
[p]fable settings relationship add "mentor" "Mentor/Student relationships"
```

### Intensity Customization

Modify intensity labels:

```ini
[p]fable settings intensity customize 1 "Just Met"
```

## 📊 Analytics

### Relationship Stats

View relationship statistics:

```ini
[p]fable relationship stats "Character"
```

Stats include:

- Most frequent relationship type
- Average intensity
- Relationship count
- Change frequency

### Network Analysis

```ini
[p]fable analyze relationships "Character"
```

Shows:

- Central connections
- Relationship clusters
- Connection patterns
- Development trends

## 🔍 Tips & Best Practices

1. **Regular Updates**

   - Keep relationship intensities current
   - Log significant events
   - Update descriptions as relationships evolve

2. **Rich Descriptions**

   - Include context in relationship descriptions
   - Note key events that affected the relationship
   - Update as the dynamic changes

3. **Visual Organization**

   - Use different relationship types appropriately
   - Maintain reasonable number of connections
   - Regular cleanup of outdated relationships

4. **Integration Tips**
   - Link relationships to story arcs
   - Use relationship events in character timelines
   - Connect relationships to locations

## 📤 Export & Backup

### Google Docs Export

```ini
[p]fable export relationships "Character" docs
```

### Visualization Export

```ini
[p]fable visualize relationships "Character" --save
```

### Full Backup

```ini
[p]fable backup relationships
```

---

For more examples and community templates, check our [Relationship Templates](Relationship-Templates) page.
