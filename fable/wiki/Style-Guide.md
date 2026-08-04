# 🎨 Style Guide

A comprehensive guide for maintaining consistent visual design across Fable's features.

## 🎨 Color Palette

### Primary Colors

```python
COLORS = {
    "PRIMARY": 0x7289DA,  # Discord Blurple - Main brand color
    "SUCCESS": 0x43B581,  # Green - Positive actions/success
    "WARNING": 0xFAA61A,  # Yellow - Warnings/cautions
    "ERROR": 0xF04747,  # Red - Errors/failures
    "INFO": 0x4F545C,  # Gray - Neutral information
    "BACKGROUND": 0x2F3136,  # Dark - Background/secondary
}
```

### Usage Guidelines

#### Character Profiles

- `PRIMARY` - Default character profile color
- `SUCCESS` - Allied/friendly relationships
- `WARNING` - Neutral/developing relationships
- `ERROR` - Rival/antagonistic relationships
- `INFO` - Background information

#### Location Embeds

- `0xC19A6B` (Brown) - Taverns/Inns
- `0x808080` (Gray) - Castles/Fortresses
- `0x43B581` (Green) - Houses/Residences
- `0xFAA61A` (Yellow) - Shops/Markets
- `0xF04747` (Red) - Dungeons/Dangerous areas
- `0x7289DA` (Blurple) - Other locations

#### Timeline Events

- `SUCCESS` - Achievements/milestones
- `PRIMARY` - Story developments
- `INFO` - General events
- `WARNING` - Important moments
- `ERROR` - Conflicts/challenges

## 🔣 Icon Usage

### Standard Icons

```
📝 Text/Description
👤 Character
🤝 Relationship
🗺️ Location
📅 Timeline
⚙️ Settings
❓ Help/FAQ
```

### Feature-Specific Icons

#### Character Development

```
🎭 Character Profile
📈 Progress/Development
🎯 Milestone
✨ Achievement
📖 Story Arc
```

#### Relationships

```
👥 Relationships Overview
💚 Ally (Level 1-5: ⭐-⭐⭐⭐⭐⭐)
❤️ Rival (Level 1-5: ⭐-⭐⭐⭐⭐⭐)
💙 Family
⚪ Neutral
🟣 Custom Types
```

#### Locations

```
🏰 Castle/Keep
🍺 Tavern/Inn
🏠 House/Residence
🏪 Shop/Market
⚔️ Dungeon
🗿 Landmark
```

#### Timeline & Events

```
📅 Timeline View
🎯 Milestone
👥 Relationship Event
📖 Story Event
📍 Location Visit
```

## 📝 Typography

### Embed Titles

- Use Title Case
- Include relevant icon
- Keep concise (< 60 characters)
- Example: `🎭 Character Profile: Aria Silverleaf`

### Field Names

- Use Title Case
- Keep short and clear
- Group related information
- Example: `📈 Current Progress` or `🗺️ Known Locations`

### Descriptions

- Use proper sentence case
- Include formatting for emphasis
- Use lists for multiple items
- Keep paragraphs short (2-3 lines)

### Code/Command Examples

- Use `ini` code blocks
- Include command prefix
- Add comments for clarity
- Show example outputs

## 📋 Layout Patterns

### Character Profiles

```
[Title] Character Name
[Thumbnail] Character Image
[Description] Brief Bio
[Fields]
- Basic Information
- Background
- Current Status
- Relationships
[Footer] Last Updated
```

### Location Cards

```
[Title] Location Name
[Image] Location Image (if available)
[Description] Location Description
[Fields]
- Notable Features
- Current Visitors
- Connected Locations
[Footer] Discovery Date
```

### Timeline Views

```
[Title] Timeline View
[Description] Time Period
[Fields]
- Recent Events (3-5)
- Upcoming Events
- Milestone Progress
[Footer] Last Updated
```

### Relationship Maps

```
[Title] Relationships
[Description] Connection Summary
[Image] Relationship Graph
[Fields]
- Key Relationships
- Recent Changes
[Footer] Total Connections
```

## 🎯 Best Practices

### Embed Design

1. **Consistency**

   - Use standard color scheme
   - Maintain icon usage patterns
   - Follow layout templates

2. **Readability**

   - Clear hierarchy
   - Proper spacing
   - Limited fields (max 25)
   - Concise descriptions

3. **Interactivity**

   - Add buttons when needed
   - Include navigation options
   - Provide clear feedback

4. **Performance**
   - Optimize image sizes
   - Limit embed size
   - Cache when possible

### Content Guidelines

1. **Text Length**

   - Titles: 40-60 characters
   - Descriptions: 100-200 characters
   - Field names: 20-30 characters
   - Field values: 50-100 characters

2. **Formatting**

   - Use bold for emphasis
   - Use inline code for commands
   - Use lists for multiple items
   - Use newlines for readability

3. **Update Frequency**
   - Refresh dynamic content
   - Show last updated time
   - Clear outdated information
   - Maintain history

## 🔄 Implementation

### Example Embed Generator

```python
def create_styled_embed(title: str, description: str, embed_type: str = "info") -> discord.Embed:
    """Generate a styled embed following guide."""
    colors = {"character": 0x7289DA, "location": 0x43B581, "timeline": 0xFAA61A, "info": 0x4F545C}

    icons = {"character": "🎭", "location": "🗺️", "timeline": "📅", "info": "ℹ️"}

    embed = discord.Embed(title=f"{icons[embed_type]} {title}", description=description, color=colors[embed_type])

    embed.set_footer(text=f"Generated • {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    return embed
```

---

By following these guidelines, we ensure a consistent and professional appearance across all of Fable's features. Remember to update this guide as new features are added or design patterns evolve.
