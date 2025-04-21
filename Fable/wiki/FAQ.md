# ❓ Frequently Asked Questions

## General Questions

### What is Fable?

Fable is a Red-Discord Bot cog that helps you create and manage rich roleplay worlds with character profiles, relationships, locations, and story tracking.

### What makes Fable different from other RP bots?

Fable focuses on narrative development and visual storytelling, with features like:

- Interactive character timelines
- Relationship visualization
- Location mapping
- Story arc tracking
- Google Docs integration

### Do I need programming knowledge to use Fable?

No! Fable is designed to be user-friendly. All features are accessible through simple Discord commands.

## Setup & Configuration

### How do I install Fable?

```ini
[p]repo add taako https://github.com/TaakoOfficial/TaakosCogs
[p]cog install TaakosCogs Fable
[p]load Fable
```

See our [Installation Guide](Installation) for detailed steps.

### Why isn't the visualization working?

The visualization features require Graphviz. Run this command to check dependencies:

```ini
[p]fable doctor
```

### How do I set up Google integration?

1. Create a Google Cloud project
2. Enable necessary APIs
3. Set up credentials
   Check our [Google Integration Guide](Google-Integration) for step-by-step instructions.

## Characters & Development

### How many characters can I create?

There's no hard limit, but we recommend keeping it manageable for your server.

### Can I import existing characters?

Yes! Use the import command:

```ini
[p]fable character import "Character" url_or_file
```

### How do I track character development?

Use milestones and story arcs:

```ini
[p]fable milestone add "Character" "Achievement" "Description"
[p]fable arc create "Arc Title" "Character" "Description"
```

## Relationships & Connections

### How do relationship intensities work?

Relationships are rated 1-5:

- 1 ⭐ - Acquaintance
- 2 ⭐⭐ - Familiar
- 3 ⭐⭐⭐ - Strong
- 4 ⭐⭐⭐⭐ - Deep
- 5 ⭐⭐⭐⭐⭐ - Unbreakable

### Can I create custom relationship types?

Yes! Admins can create server-specific types:

```ini
[p]fable settings relationship add "type_name" "description"
```

### Why is my relationship graph cluttered?

Try filtering or using the force layout:

```ini
[p]fable visualize relationships "Character" --filter allies
[p]fable visualize layout set force
```

## Locations & World Building

### How do I connect locations?

Use the connect command:

```ini
[p]fable location connect "Location1" "Location2" "Description"
```

### Can I create private locations?

Yes, use access settings:

```ini
[p]fable location access set "Location" restricted "Guild members only"
```

### How do I track character visits?

Record visits with:

```ini
[p]fable location visit "Location" "Character" "Optional note"
```

## Data & Backups

### How do I backup my data?

Several options:

```ini
# Full backup
[p]fable backup all

# Specific backup
[p]fable backup characters
[p]fable backup locations
```

### Can I export to Google Docs?

Yes! With Google integration enabled:

```ini
[p]fable export character "Character" docs
[p]fable export timeline "Character" docs
```

### How often should I backup?

We recommend:

- Weekly full backups
- Daily character backups
- After major events
- Before large changes

## Permissions & Management

### Who can create characters?

By default, all users can create characters, but admins can restrict this:

```ini
[p]fable settings permissions character_creation admin_only
```

### How do I manage inactive characters?

Use the archive feature:

```ini
[p]fable character archive "Character" "Reason"
```

### Can I delete data?

Admins can remove data:

```ini
[p]fable character delete "Character"
[p]fable location delete "Location"
```

## Customization & Themes

### Can I customize embed colors?

Yes, set theme colors:

```ini
[p]fable settings colors set character #7289DA
```

### How do I change timeline icons?

Customize event icons:

```ini
[p]fable timeline icons customize
```

### Can I create custom templates?

Yes! Share templates with:

```ini
[p]fable template create "Template Name"
[p]fable template share "Template Name"
```

## Still Need Help?

- Check our [Troubleshooting Guide](Troubleshooting)
- Join our [Discord Support Server](https://discord.gg/example)
- Open an [Issue on GitHub](https://github.com/TaakoOfficial/TaakosCogs/issues)
