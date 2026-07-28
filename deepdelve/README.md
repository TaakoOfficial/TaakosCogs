# deepdelve

A persistent, button-driven old-school text RPG for Red-DiscordBot.

![DeepDelve key art](./assets/deepdelve-key-art.png)

[Back to the cog catalog](../README.md)

## The Game

Beneath Lastlight Outpost lies the Deep: an endless dungeon of monsters, treasure,
traps, forgotten shrines, consequential mysteries, and sealed boss chambers. Every
member creates a persistent character and explores one room at a time through Discord
embeds and buttons.

The central loop is:

```text
Explore → encounter → choose an action → earn loot → equip upgrades → descend
```

Progress is saved after every action. An interrupted battle can be resumed with
`[p]deepdelve adventure`.

## Install

```text
[p]repo add taakoscogs https://github.com/TaakoOfficial/TaakosCogs
[p]cog install taakoscogs deepdelve
[p]load deepdelve
```

Start a character:

```text
[p]deepdelve create
```

All player commands are hybrid commands and can also be used through Discord slash
commands, such as `/deepdelve adventure`.

## Classes

| Class | Style | Signature Skill |
| --- | --- | --- |
| Vanguard | High health and defense | Shield Bash deals heavy damage and weakens enemies |
| Shadow | High attack, luck, and critical chance | Twin Fang performs two critical-capable strikes |
| Arcanist | High mana and spell damage | Arcane Lance ignores most enemy armor |

Prefix users can create a named character directly:

```text
[p]deepdelve create shadow Nyx
```

Without arguments, character creation uses an interactive class selector and the
member's current display name.

## Highlights

- Persistent per-server characters and saved combat encounters.
- Button-driven exploration, combat, inventory, and town services.
- Five authored regions with distinct atmosphere, narration, lore, and materials.
- Consequence-bearing decisions influenced by class, attributes, items, and currency.
- Scalable enemies with named bosses on every fifth floor.
- Elite enemies with armor, frenzy, venom, life drain, or ancient power.
- Telegraphed enemy intentions, Defend, cooldowns, four abilities per class, and tactical conditions.
- Five attributes, class talent trees, nine subclasses, backgrounds, alignments, titles, scars, and blessings.
- Procedurally generated weapons, armor, and charms with prefixes, suffixes, sets, curses, and identification.
- Common, Uncommon, Rare, Epic, and Legendary equipment.
- Legendary effects, set bonuses, inspection comparisons, +10 upgrades, shards, enchanting, and rerolling.
- Lastlight contracts, reputation, crafting materials, and a depth-scaled forge.
- Ten hidden lore fragments and a personal expedition journal.
- Four recurring NPCs with relationship levels and multi-stage personal quests.
- Four-member parties with cooperative roles and stat bonuses.
- Equipment auctions and persistent player guilds with perks, rankings, and shared vaults.
- Consensual arena wagers with escrow, records, and seasonal points.
- Server-wide raid bosses with contribution rankings and distributed rewards.
- Deterministic daily dungeons, five-wave rifts, seasonal ladders, and server-first records.
- Hardcore permanent death, Ascension, prestige, and permanent endgame rewards.
- Daily exploration turns that reset at midnight UTC.
- Experience, levels, gold, death penalties, and unlimited dungeon scaling.
- Achievements with gold rewards and personal creature bestiaries.
- Depth, level, kill, gold, and boss leaderboards.
- Configurable adventure channel and daily turn allowance.
- No external services or Python dependencies.

## Player Commands

| Command | Description |
| --- | --- |
| `[p]deepdelve` | Open the current adventure panel |
| `[p]deepdelve create [class] [name]` | Create a character |
| `[p]deepdelve adventure` | Explore a room or resume battle |
| `[p]deepdelve profile [member]` | View a character sheet |
| `[p]deepdelve inventory` | Equip and sell collected gear |
| `[p]deepdelve town` | Heal, restore mana, and buy potions |
| `[p]deepdelve achievements [member]` | View achievement progress |
| `[p]deepdelve bestiary` | View discovered enemies |
| `[p]deepdelve lore` | Read recovered lore fragments |
| `[p]deepdelve journal` | Read recent expedition history |
| `[p]deepdelve materials` | View crafting resources |
| `[p]deepdelve contract` | Visit the Lastlight contract board |
| `[p]deepdelve craft` | Forge a weapon, armor, or charm |
| `[p]deepdelve regions` | View discovered dungeon regions |
| `[p]deepdelve leaderboard [category]` | View server rankings |
| `[p]deepdelve retire` | Permanently delete your character |

`[p]delve` is a shorter alias for the main command.

## Advanced Command Groups

| Group | Systems |
| --- | --- |
| `[p]deepdelve progression` | Attributes, talents, backgrounds, alignment, subclass, title, and respec |
| `[p]deepdelve item` | Inspection, codex, sets, identification, and curse cleansing |
| `[p]deepdelve npc` | Lastlight characters, relationships, and story quests |
| `[p]deepdelve party` | Party creation, joining, leaving, status, and cooperative roles |
| `[p]deepdelve auction` | Browse, list, buy, and cancel fixed-price equipment listings |
| `[p]deepdelve guild` | Player guilds, contributions, perks, rankings, and shared vaults |
| `[p]deepdelve arena` | Challenges, escrowed wagers, acceptance, declining, and cancellation |
| `[p]deepdelve endgame` | Rifts, daily dungeons, Hardcore, Ascension, seasons, and world bosses |

Use `[p]help deepdelve <group>` to see every subcommand and argument.

## Tactical Combat

Enemies reveal their next intention before every action. Intentions include measured
strikes, crushing blows, multi-hit flurries, defensive stances, curses, and healing.
Players can attack, defend, use a potion, flee, or choose an unlocked ability from the
combat selector.

Every class unlocks abilities at levels 1, 4, 7, and 12. Leveling grants attribute
points and regular talent points. At level 10, each base class chooses one of three
permanent subclasses:

- Vanguard: Guardian, Berserker, or Warlord
- Shadow: Assassin, Duelist, or Trickster
- Arcanist: Elementalist, Necromancer, or Chronomancer

## Advanced Equipment

Equipment can carry a prefix, suffix, set identity, enchantment, binding, curse, or
legendary power. Rare relics may initially be unidentified. Inventory controls support
equipping, selling, dismantling, upgrading, enchanting, and rerolling. Item commands
provide detailed inspection, identification, curse cleansing, set bonuses, and the
permanent relic codex.

## Multiplayer and Endgame

Parties hold up to four delvers. Cooperative roles—Guardian, Striker, Support, and
Scout—add distinct bonuses. Player guilds level through contributions and world-boss
activity, unlocking economy, Luck, daily-turn, and raid-damage perks.

Arena wagers are consensual and escrowed: currency is withdrawn when a challenge is
created, paid only after acceptance, and refundable through decline or cancellation.
The auction house transfers real equipment and uses the selected DeepDelve economy.

Challenge rifts contain five escalating waves. Daily dungeons are deterministically
seeded from the UTC date so every server receives the same challenge and modifier.
World bosses are shared server encounters with individual attack cooldowns and
contribution-based rewards.

Ascension becomes available after floor 20 and four bosses. It resets combat
progression for permanent prestige and blessings while preserving lore, codex,
achievements, currency, reputation, titles, and social membership. Hardcore mode is
optional and must be selected before the first kill; a Hardcore combat death
permanently seals that character.

## Server Settings

Administrators and members with Manage Server can configure the game:

```text
[p]deepdelve set
[p]deepdelve set enabled true
[p]deepdelve set channel #adventures
[p]deepdelve set channel
[p]deepdelve set turns 24
[p]deepdelve set economy bank
[p]deepdelve set resetuser @member
```

The channel restriction applies to both commands and interactive exploration
buttons. Daily turns may be configured from 5 to 100.

## Red Economy Integration

DeepDelve supports two per-server economy modes:

```text
[p]deepdelve set economy internal
[p]deepdelve set economy bank
```

- `internal` is the default and keeps dungeon gold isolated inside DeepDelve.
- `bank` uses Red's configured bank balance and currency name for the entire game.

In bank mode, monster and boss rewards, treasure, item sales, contracts,
achievements, crafting costs, town purchases, narrative choices, and death penalties
all directly affect the member's Red bank account. Gold leaderboards also read live
bank balances.

Balance changes are applied as transaction deltas. If another economy cog changes a
member's balance while an adventure is active, DeepDelve adds or subtracts only its
own transaction rather than replacing the outside change. Rewards respect Red's
configured maximum bank balance.

Switching to bank mode does not deposit existing internal dungeon gold. It becomes
inactive while the game uses the member's existing bank balance. Switching back uses
the character's most recently cached balance as internal gold.

## Gameplay Notes

- Exploring a new room costs one turn; combat actions do not.
- A floor contains five rooms. Every fifth floor ends with a boss.
- Fleeing becomes easier with Luck, but bosses are harder to escape.
- A normal defeated character loses 15% of their currency, gains a scar, retreats one
  floor, and is restored at Lastlight. Hardcore deaths are permanent.
- Equipment packs hold 25 items. Loot found while full is converted into gold.
- Town prices scale gently with character level.
- Region-specific materials drop from enemies and bosses. The forge consumes three
  units of the current region's material.
- Narrative encounters remain saved until the member makes a decision.
- Contracts progress through enemy victories and award reputation alongside currency
  and experience.

## Permissions

The bot needs:

- Send Messages
- Embed Links
- Use External Emojis (only if required by the server's emoji configuration)

No privileged Discord intents are required.

## Data and Privacy

DeepDelve stores Discord user IDs and persistent game state per server. Stored data
includes character details, attributes, inventory, equipment, currency cache, dungeon
progress, active encounters and choices, conditions, crafting materials, contracts,
reputation, NPC stories, lore, journal entries, titles, scars, blessings,
achievements, social membership, arena records, endgame progress, seasonal progress,
and discovered enemies. Server configuration also stores party, auction, player-guild
and shared-vault, arena, world-boss, and server-first records. When bank mode is
enabled, DeepDelve reads and changes the member's Red bank balance for game
transactions.

The cog implements Red's user-data export and deletion hooks. Players can also delete
their current server character directly with `[p]deepdelve retire`. No game data is
sent to an external service.

## Project Structure

DeepDelve is divided into focused modules:

- `content.py` contains original regions, enemies, bosses, events, and base loot.
- `advanced_content.py` contains abilities, talents, subclasses, sets, legendaries, NPCs, and seasons.
- `systems/combat.py` handles enemy intentions.
- `systems/progression.py` calculates builds, titles, subclasses, talents, scars, and blessings.
- `systems/items.py` handles advanced procedural itemization and equipment operations.
- `systems/story.py` evaluates NPC relationships and story quests.
- `systems/social.py` supports parties, player guilds, arena ratings, and record IDs.
- `systems/endgame.py` produces seasons and deterministic daily challenges.
- `deepdelve.py` owns Red commands, persistence orchestration, and Discord interactions.

## Dashboard

DeepDelve registers a read-only Red-Web-Dashboard page showing server settings and
available commands. Individual player profiles are intentionally excluded.
