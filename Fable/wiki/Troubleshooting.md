# 🔧 Troubleshooting Guide

## Common Issues & Solutions

### 🚫 Installation Issues

#### Bot doesn't recognize Fable commands

```ini
# Try reloading the cog
[p]reload Fable

# If that fails, unload and load
[p]unload Fable
[p]load Fable
```

#### Missing dependencies

```ini
# Check dependencies
[p]fable doctor

# Manual package installation
python3 -m pip install graphviz
```

### 📊 Visualization Problems

#### Graphs not generating

1. Check Graphviz installation

```ini
[p]fable visualize test
```

2. Clear visualization cache

```ini
[p]fable visualize cache clear
```

3. Try different layout

```ini
[p]fable visualize layout set grid
```

#### Timeline not updating

1. Refresh timeline data

```ini
[p]fable timeline refresh "Character"
```

2. Check event permissions

```ini
[p]fable timeline check "Character"
```

### 💾 Data Issues

#### Character data not saving

1. Check Config system

```ini
[p]fable debug config
```

2. Force save

```ini
[p]fable character forcesave "Character"
```

#### Lost relationships

1. Check relationship cache

```ini
[p]fable relationship debug "Character"
```

2. Rebuild connections

```ini
[p]fable relationship rebuild "Character"
```

### 🌐 Google Integration

#### Sync not working

1. Verify credentials

```ini
[p]fable google test
```

2. Check permissions

```ini
[p]fable google permissions
```

3. Reset connection

```ini
[p]fable google reset
```

### 🎨 Display Issues

#### Embeds not showing

1. Check bot permissions
2. Verify embed links permission
3. Try compact mode

```ini
[p]fable display compact
```

#### Missing images

1. Check Discord CDN status
2. Try re-uploading images
3. Use alternate hosting

## 🔍 Diagnostic Tools

### System Check

```ini
# Full system check
[p]fable doctor

# Component checks
[p]fable doctor visualization
[p]fable doctor storage
[p]fable doctor google
```

### Debug Information

```ini
# Get debug info
[p]fable debug info

# Check specific component
[p]fable debug component_name
```

### Log Analysis

```ini
# View recent errors
[p]fable logs show

# Export logs
[p]fable logs export
```

## 🔄 Reset Options

### Soft Reset

```ini
# Reset settings
[p]fable settings reset

# Clear caches
[p]fable cache clear
```

### Hard Reset

```ini
# Reset specific component
[p]fable reset component_name

# Full reset (admin only)
[p]fable reset all
```

## 🚨 Error Messages

### Common Error Codes

#### FABLE-001: Configuration Error

- Check Config system
- Verify file permissions
- Reset config if needed

#### FABLE-002: Visualization Error

- Verify Graphviz installation
- Check file permissions
- Clear visualization cache

#### FABLE-003: Data Storage Error

- Check disk space
- Verify write permissions
- Backup and restore data

## 🆘 Getting Help

### Quick Fixes

1. Reload the cog
2. Clear cache
3. Check permissions
4. Update dependencies

### Advanced Troubleshooting

1. Export debug logs
2. Check system requirements
3. Verify file integrity
4. Test in isolation

### Support Resources

- [Discord Support Server](https://discord.gg/example)
- [GitHub Issues](https://github.com/TaakoOfficial/TaakosCogs/issues)
- [Documentation](https://github.com/TaakoOfficial/TaakosCogs/wiki)

## 🔐 Permission Issues

### Bot Permissions

Required permissions:

- Send Messages
- Embed Links
- Attach Files
- Add Reactions
- Use External Emojis

### User Permissions

Common permission issues:

- Character creation restrictions
- Location management
- Relationship settings
- Export permissions

## 🔍 Performance Issues

### Slow Commands

1. Clear command cache
2. Update indexes
3. Optimize database

### Memory Usage

1. Clear unused data
2. Archive old records
3. Optimize storage

## 🔄 Recovery Options

### Data Recovery

```ini
# Restore from backup
[p]fable restore backup_name

# Import from file
[p]fable import file_name
```

### Emergency Fixes

```ini
# Emergency mode
[p]fable emergency

# Safe mode
[p]fable safemode
```

## 📝 Reporting Issues

When reporting issues, include:

1. Error message
2. Command used
3. Debug logs
4. Steps to reproduce

Submit issues on [GitHub](https://github.com/TaakoOfficial/TaakosCogs/issues) with the template.
