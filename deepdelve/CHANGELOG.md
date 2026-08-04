# Changelog

All notable changes to `deepdelve` are documented here.

## 5.0.2

- Replaced the talent selector's non-emoji diamond glyph with a Discord-valid
  Unicode emoji, preventing `50035 Invalid Form Body` failures when opening the
  Progression hub screen.
- Added regression coverage for the exact serialized select-option payload sent
  to Discord.

## 5.0.1

- Increased the default daily exploration allowance from 24 to 40 turns while
  preserving the configurable 5–100 turn range.
- Replaced fixed UTC reset text with Discord timestamps that display the next
  daily reset in each player's local time alongside a relative countdown.
- Added context-aware inventory controls, exact upgrade previews, richer power,
  effect, and set comparisons, menu-based favorite protection, and safe
  confirmations for valuable sales and dismantling.
- Added a secondary Armory menu with persistent sorting and filtering, visible
  loadout/vault status, protected bulk dismantling, and configurable salvage rules.
- Added confirmed enchanting with a standard random sigil or a deterministic
  player-selected sigil at double shard cost, including replacement warnings.
- Added a persistent Activities hub so professions, gathering, companions, weekly
  commissions, the Living Chronicle, and seasonal chapters are playable from menus.
- Added menu controls for accepting and resolving quests, entering and advancing
  named dungeons, resolving Atlas rooms, resuming battles, and abandoning routes.
- Added inventory identification with a visible arcane-shard cost and an Identify
  button for unidentified drops.
- Smoothed the floor 6–9 enemy, elite, and miniboss endurance transition so the
  second region no longer creates a sudden progression wall.
- Fixed the permanent Season Archive screen reading the wrong completion-state key.
- Fixed puzzle and riddle text appearing twice when a chamber was first discovered.
- Doubled the procedural puzzle catalog to 50 entries, with ten distinct puzzles
  available in every floor band and protection against immediate repeats.
- Added optimized illustrated portraits for all 26 core creatures and seven bosses;
  elite, Riftbound, Ascended, and named-dungeon variants inherit suitable artwork.
- Extended persistent-view reconstruction coverage for every new button and selector.

## 5.0.0

- Added the persistent Living World hub with restart-safe Resume, Quests, Atlas,
  Character, Inventory, Morality, Codex, Town, Mail, and Sanctum navigation.
- Added a six-act, 36-scene Living Chronicle with 18 permanent decisions and four
  endings; three eight-quest faction arcs; nine personal arcs; a persistent journal;
  World Echoes; relationship memories; mail; and a solo Nemesis system.
- Made Morality playable through unique-source Resolve, 18 capped Tenet sidegrades,
  a rotating Oath Board, equal-value faction services, three-stage moral journeys,
  reactive presentation, and normalized once-per-encounter invocations.
- Added an Atlas and ten named branching dungeons, 60 authored events, 15 multi-route
  puzzles, 45 enemies, 15 elite identities, 10 bosses, and permanent consequence flags.
- Added 12 equipment sets, 30 named relics, 24 consumables, 30 recipes, 36 contracts,
  12 permanent seasonal chapters, weekly commissions, recipe research, and a capped
  five-room Sanctum currency sink.
- Advanced profiles to schema 8 and guilds to schema 6 with idempotent migrations,
  historical unique-deed Resolve credit, preserved old custom IDs, per-character
  locks, immediate interaction deferral, and idempotent reward claims.
- Closed duplicate campaign payouts, full-satchel faction charges, resale/arbitrage
  paths, repeatable Resolve farming, and stale-state interaction races.
- Added registry validation, 7/30/90-day economy projections, migration and duplicate
  claim coverage, and an all-class/subclass/morality Monte Carlo release gate.

## 4.3.6

- Bypassed Red Config's unsafe recursive merge for member profiles, which crashed
  when a saved equipment item was overlaid onto a registered `None` slot.
- Added a non-mutating raw-data/default overlay and routed every direct member-profile
  read through it, including commands, character creation, and social bonus syncs.

## 4.3.5

- Replaced the finished-view workaround with discord.py's supported fully dynamic
  view model, restoring normal command panel delivery.
- Player panels now contain dynamic items directly: they render as ordinary Discord
  controls, register no competing live callbacks, and remain restart-safe.

## 4.3.4

- Made legacy live-view cleanup optional and non-fatal across differing Red and
  discord.py internal view-store implementations.
- Isolated per-view cleanup failures so compatibility differences cannot prevent the
  cog from loading.

## 4.3.3

- Made dynamic routing the sole handler for all player buttons and selectors instead
  of registering a second live callback for newly posted messages.
- Purges legacy message-bound DeepDelve views during unload and load, preventing stale
  cog instances from receiving interactions after an update.
- Encodes inventory selections into owner-bound action routes so inventory management
  remains fully stateful without live views.

## 4.3.2

- Replaced the response-timing heuristic with an exact message-bound view-registry
  check, preventing restart recovery from racing any live button or selector.
- Added a narrow safeguard for Discord's harmless `InteractionResponded` exception
  without suppressing genuine component failures.

## 4.3.1

- Fixed every live component interaction being dispatched a second time through
  restart recovery, which produced a false “unexpected snag” response after valid clicks.
- Live stateful views now receive first refusal, while dynamic buttons and selectors
  continue to recover genuinely orphaned messages after cog reloads and bot restarts.

## 4.3.0

- Split native item powers from enchantment powers and added schema-v7 profile and
  schema-v5 guild migrations for inventories, equipment, stashes, auctions, and guild vaults.
- Made forge patterns deterministic and protected origin, legendary, boss, set, and
  bound identities from destructive rerolls.
- Added permanent legendary/set records, set-drop pity, weaker-duplicate conversion,
  set fragments, and deterministic missing-piece forging.
- Added two-victory Conviction Fatigue with boss, camp, inn, and Ascension recovery.
- Normalized bestiary entries by authored identity while retaining elite variants,
  encounter depth ranges, and separate boss/miniboss sections.
- Extended normal, elite, miniboss, and early-boss durability and added modest
  post-victory mana recovery for tactical pacing without removing resource pressure.
- Improved item inspection, collections, loadouts, and morality panels with permanent
  discoveries, real item names, enchantment details, and visible fatigue state.
- Expanded the balance harness with normal, elite, miniboss, and boss target bands
  plus a prepared five-combat attrition stress test across milestone floors and every class.

## 4.2.0

- Replaced static good-and-evil labeling with Living Morality from −100 Umbral to
  +100 Radiant while preserving alignment as the character's origin philosophy.
- Added Mercy, Honesty, Ambition, and Ruthlessness convictions so characters sharing
  a moral path can still develop distinct identities.
- Added a permanent forty-entry Book of Deeds covering campaign decisions and
  consequential dungeon encounters, with capped diminishing returns that prevent
  easy morality farming.
- Added five visible moral transformations, reactive character-sheet colors and
  descriptions, authored reactions from every major NPC, altered shrine responses,
  and morality-aware wanderer encounters.
- Added Lantern Grace, Measured Gambit, and Dread Claim as balanced once-per-battle
  Conviction powers with stronger forms at extreme morality.
- Added the Mirror of Judgment, whose three solutions are gated by Radiant, balanced,
  or Umbral morality, plus three morality-earned titles.
- Added schema-v6 backfilling that reconstructs morality and story deeds from existing
  campaign choices without changing established origin data.

## 4.1.0

- Added a persistent three-part origin sequence with backgrounds, alignments, and
  nine class-specific starter weapons whose restrained effects shape early builds.
- Added 45 authored regional equipment bases, 20 new affixes, nine subclass sets,
  21 source-matched boss relics, item comparisons, loot pity, and relic pity.
- Added a 60-slot vault, three named loadouts, favorites, protected auto-dismantle,
  collection tracking, five rumor-unlocked forge patterns, and exploit-safe resets.
- Added 15 tactical consumables with a persistent combat selector and safe
  out-of-combat restorative use.
- Added deterministic floor conditions, five named minibosses, hidden rooms,
  impossible camps, personal rumor hunts, recipe rewards, and bestiary mastery.
- Added story relics for campaign decisions, boss run history, and personalized
  chronicle recaps.
- Expanded combat identities for origin weapons, authored affixes, sets, boss
  relics, two-phase boss escalation, and floor-condition tactics.
- Added schema-v5 migrations and regression coverage for origins, collections,
  armory safeguards, consumables, rumors, relics, mutators, and persistent controls.

## 4.0.1

- Rebuilt enemy durability and boss progression around longer tactical encounters,
  including a monotonic Ascended boss curve with no floor-40 identity reset.
- Reduced Vanguard damage, made Retaliation functional, corrected solo Warlord
  bonuses, and gave bosses stronger armor penetration.
- Changed cooldowns to advance after completed actions, reduced defensive and Mote
  mana recovery, and preserved meaningful resource pressure between encounters.
- Safely restores interrupted adventure state after challenge death or escape,
  prevents ascension with unresolved content, and brackets daily dungeons to player
  progression.
- Removed companion-selection bond farming, capped prestige combat power, and made
  scars narrative records instead of intentional-death stat rewards.
- Prevented upgraded equipment from manufacturing resale currency, slowed monster,
  contract, challenge, and overflow rewards, and strengthened service and crafting
  gold sinks.
- Added regression coverage and a repeatable Monte Carlo combat simulator for the
  new balance bands.
- Made player-owned adventure, combat, town, crafting, inventory, choice, puzzle,
  and campaign controls persistent across timeouts, cog reloads, and bot restarts
  through owner-bound dynamic component IDs.

## 4.0.0

- Added The Living Chronicle, a five-chapter branching campaign with fifteen authored
  scenes, permanent decisions, multiple endings, mechanical choice bonuses, rewards,
  and a completion title.
- Added five interactive regional puzzle chambers with saved attempts, hints, damage
  consequences, unique completion tracking, streaks, and scalable rewards.
- Added five collectible companions with milestone discovery, active selection,
  levels, bond, statistics, combat progression, and distinct exploration passives.
- Added Blacksmith, Alchemist, Cartographer, and Relic Hunter professions with 25
  levels, five ranks, preserved mastery, daily gathering, and unique benefits.
- Added server-wide Lastlight development with contributions, treasury, four
  upgradeable buildings, sixteen upgrade tiers, and mechanical town benefits.
- Added five deterministic daily world events that alter enemy strength, rewards,
  puzzle frequency, and expedition atmosphere.
- Added ten enemies, three late-game bosses, ten lore fragments, five consequence
  encounters, evolving NPC dialogue, and four new achievements.
- Added the five-part Delver's Primer and contextual onboarding on new profiles.
- Added automatic versioned migrations, persistent world-boss controls, expanded
  privacy export/deletion, and configurable 0.75×–2.00× server difficulty.
- Added original campaign, Lastlight, and companion artwork with rich embed integration.
- Split campaign, puzzle, companion, profession, world, migration, and expansion
  content into focused modules and added regression tests for their pure systems.

## 3.0.0

- Added tactical enemy intentions with Strike, Heavy, Flurry, Guard, Hex, and Renewal actions.
- Replaced the single class-skill button with an ability selector and four unlockable abilities per class.
- Added Defend, cooldowns, barriers, evasion, retaliation, armor destruction, Burn, Poison, Curse, and Mana Shield.
- Added five attributes, spendable points, three class talent trees, and build respecialization.
- Added nine permanent subclasses with bonuses and passive combat identities.
- Added selectable character backgrounds, alignments, titles, scars, and permanent blessings.
- Added item prefixes, suffixes, set pieces, set bonuses, legendary relics, unique effects, binding, curses, and unidentified gear.
- Added inspection comparisons, a relic codex, +10 upgrades, dismantling, arcane shards, enchanting, rerolling, identifying, and cleansing.
- Added dungeon-map breadcrumbs and expanded branching narrative support.
- Added Orra, Mara, Vesper, and Rook as recurring NPCs with relationships and story-quest chains.
- Added four-member parties, cooperative roles, and party stat bonuses.
- Added a fixed-price equipment auction house compatible with both internal and Red bank economies.
- Added persistent player guilds, levels, perks, treasury, renown, rankings, and shared equipment vaults.
- Added consensual arena challenges with escrowed wagers, records, power ratings, cancellation, and seasonal rewards.
- Added server-wide world bosses with per-player cooldowns, damage rankings, distributed rewards, and guild renown.
- Added deterministic daily dungeons, modifiers, five-wave challenge rifts, and difficulty scaling.
- Added Hardcore characters, permanent death chronicles, Ascension, prestige, seasonal ladders, and server-first boss records.
- Added original DeepDelve key art and a more tactical, information-rich embed presentation.
- Split advanced content and gameplay helpers into progression, combat, item, story, social, and endgame modules.
- Expanded Red data export and deletion coverage to include all multiplayer and social records.

## 2.0.0

- Added optional, per-server Red bank integration as a complete economy backend.
- Added safe balance-delta commits so unrelated Red economy transactions are preserved.
- Added support for the bank's configured currency name and maximum balance.
- Added five atmospheric dungeon regions with unique narration and crafting materials.
- Added elite Armored, Frenzied, Venomous, Vampiric, and Ancient enemies.
- Added persistent poison and curse conditions plus life-draining enemies.
- Added consequential narrative encounters with class-, attribute-, item-, and currency-based outcomes.
- Added ten discoverable lore fragments and a rolling personal expedition journal.
- Added Lastlight reputation, repeatable contracts, progress tracking, and contract rewards.
- Added region materials and depth-scaled weapon, armor, and charm crafting.
- Added lore, journal, materials, contract, craft, regions, and economy configuration commands.
- Added achievements for contracts, lore discovery, and crafting.

## 1.0.0

- Added persistent Vanguard, Shadow, and Arcanist characters.
- Added button-driven dungeon exploration and turn-based combat.
- Added sixteen scalable enemies and recurring authored boss encounters.
- Added procedural weapons, armor, and charms across five rarity tiers.
- Added inventory selection, equipping, selling, potions, and town services.
- Added experience, leveling, gold, daily exploration turns, and death penalties.
- Added achievements, a personal bestiary, and five leaderboard categories.
- Added configurable gameplay channel, daily turns, and enable state.
- Added Red data export/deletion support and read-only dashboard integration.
