# 📚 Examples & Showcases

Real-world examples of how to use Fable effectively in your roleplay community.

## 👤 Character Examples

### Fantasy Character: Aria Silverleaf

```ini
[p]fable character create "Aria Silverleaf" "An elven spy from the mystical Silverwood, known for her cunning and mastery of ancient magic."
```

#### Profile Highlights

```ini
Species: High Elf
Occupation: Spy/Arcane Scholar
Age: 247
Alignment: Neutral Good
Languages: Common, Elvish, Draconic
```

#### Development Timeline

```ini
[p]fable milestone add "Aria" "Personal Growth" "Discovered ancient spell tome in ruins"
[p]fable milestone add "Aria" "Achievement" "Became Silverwood's Master of Secrets"
[p]fable arc create "Path of Ancient Magic" "Aria" "Quest to unlock forgotten elven magic"
```

#### Relationships

```ini
[p]fable relationship set "Aria" "Bram Ironweave" rival 4 "Competitive artifact hunters with a complex history"
[p]fable relationship set "Aria" "Elder Moonshadow" mentor 5 "Ancient elven teacher and guide"
```

### Modern Character: Jake Chen

```ini
[p]fable character create "Jake Chen" "A tech startup founder balancing innovation with ethical AI development."
```

#### Profile Development

```ini
[p]fable character edit "Jake" background "Started coding at 12, founded TechFuture at 25"
[p]fable character edit "Jake" goals "Create ethical AI that benefits humanity"
```

#### Story Arc

```ini
[p]fable arc create "Silicon Valley Dreams" "Jake" "Journey from garage startup to tech leader"
[p]fable arc milestone add "Silicon Valley Dreams" "Jake" "First investor meeting"
```

## 🗺️ Location Examples

### Mystical Location: The Silverwood Library

```ini
[p]fable location create "Silverwood Library" magical "Ancient repository of elven knowledge, hidden within the living trees."
```

#### Features

```ini
[p]fable location feature add "Silverwood Library" "Living Books" "Magical tomes that respond to readers' thoughts"
[p]fable location feature add "Silverwood Library" "Time Pools" "Reflecting pools showing historical events"
```

#### Connected Locations

```ini
[p]fable location connect "Silverwood Library" "Arcane Archives" "Hidden portal in the restricted section"
[p]fable location connect "Silverwood Library" "Elder's Grove" "Ancient path through the heart of the forest"
```

### Modern Location: TechFuture HQ

```ini
[p]fable location create "TechFuture HQ" corporate "Modern tech campus with cutting-edge AI research facilities."
```

#### Activity Tracking

```ini
[p]fable location visit "TechFuture HQ" "Jake" "Emergency board meeting about AI breakthrough"
[p]fable location event "TechFuture HQ" "AI Ethics Summit" @Jake @Dr.Sarah @Professor.Liu
```

## 📈 Relationship Network Example

### The Silverwood Council

```ini
# Core relationships
[p]fable relationship set "Elder Moonshadow" "Aria" mentor
[p]fable relationship set "Aria" "Keeper Swiftshadow" ally
[p]fable relationship set "Keeper Swiftshadow" "Elder Moonshadow" advisor

# Visualize network
[p]fable visualize relationships --group "Silverwood Council"
```

### Tech Industry Network

```ini
# Business relationships
[p]fable relationship set "Jake" "Dr.Sarah" mentor
[p]fable relationship set "Jake" "RivalCorp CEO" rival
[p]fable relationship set "Dr.Sarah" "Professor.Liu" colleague

# Generate graph
[p]fable visualize relationships --group "Tech Industry"
```

## 📖 Story Arc Examples

### Fantasy Campaign: "Secrets of the Silverwood"

```ini
# Main arc
[p]fable arc create "Secrets of the Silverwood" "Aria" "Uncovering ancient magic threatening the forest"

# Milestones
[p]fable arc milestone add "Secrets of the Silverwood" "Aria" "Discovery of corrupted ley lines"
[p]fable arc milestone add "Secrets of the Silverwood" "Aria" "Confrontation with shadow cult"
[p]fable arc milestone add "Secrets of the Silverwood" "Aria" "Alliance with forest spirits"
```

### Modern Drama: "Silicon Valley Revolution"

```ini
# Main arc
[p]fable arc create "Silicon Valley Revolution" "Jake" "Ethical AI development faces corporate espionage"

# Events
[p]fable arc event add "Silicon Valley Revolution" "AI anomaly detected"
[p]fable arc event add "Silicon Valley Revolution" "Whistleblower revelation"
[p]fable arc event add "Silicon Valley Revolution" "Congressional hearing"
```

## 📊 Visualization Examples

### Character Timeline

```ini
# Generate visual timeline
[p]fable visualize timeline "Aria"

# Export development chart
[p]fable visualize development "Aria" --save "aria_development.png"
```

### Location Network

```ini
# Create location map
[p]fable visualize locations --region "Silverwood"

# Export as high-quality image
[p]fable visualize locations --quality high --save "silverwood_map.png"
```

## 🎭 Interactive Roleplay Examples

### Scene Setup

```ini
# Create scene
[p]fable scene create "Silverwood Library" "Ancient Secrets" "Late night research leads to unexpected discovery"

# Add participants
[p]fable scene addchar "Ancient Secrets" @Aria @Elder.Moonshadow

# Track events
[p]fable scene event "Ancient Secrets" "Discovery of hidden prophecy"
```

### Event Management

```ini
# Schedule event
[p]fable event schedule "TechFuture HQ" "AI Ethics Summit" "2025-05-01 14:00"

# Add participants
[p]fable event addchar "AI Ethics Summit" @Jake @Dr.Sarah @Professor.Liu

# Record outcomes
[p]fable event conclude "AI Ethics Summit" "New ethical guidelines established"
```

## 📤 Export Examples

### Character Documentation

```ini
# Export character profile
[p]fable export character "Aria" docs

# Export development history
[p]fable export timeline "Aria" docs
```

### World Documentation

```ini
# Export location network
[p]fable export locations docs

# Export relationship web
[p]fable export relationships docs
```

---

These examples showcase real usage patterns. Adapt them to your needs and create your own amazing stories!
