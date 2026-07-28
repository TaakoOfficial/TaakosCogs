"""Advanced progression, story, item, and endgame content for DeepDelve."""

from __future__ import annotations

from typing import Any

BACKGROUNDS: dict[str, dict[str, Any]] = {
    "soldier": {
        "name": "Lastlight Soldier",
        "emoji": "🎖️",
        "description": "You served on the walls before choosing to descend.",
        "attributes": {"might": 2, "vitality": 1},
        "gold": 0,
        "potions": 1,
    },
    "urchin": {
        "name": "Lantern Urchin",
        "emoji": "🗝️",
        "description": "You learned every hidden road and dishonest lock in Lastlight.",
        "attributes": {"finesse": 2, "fortune": 1},
        "gold": 25,
        "potions": 0,
    },
    "scholar": {
        "name": "Forbidden Scholar",
        "emoji": "📚",
        "description": "The college expelled you for proving the Deep could dream.",
        "attributes": {"insight": 2, "fortune": 1},
        "gold": 10,
        "potions": 0,
    },
}

SUBCLASSES: dict[str, dict[str, dict[str, Any]]] = {
    "vanguard": {
        "guardian": {
            "name": "Guardian",
            "emoji": "🏰",
            "description": "An immovable protector who converts guarding into retaliation.",
            "bonuses": {"hp": 30, "defense": 5},
            "passive": "Thorns",
        },
        "berserker": {
            "name": "Berserker",
            "emoji": "🪓",
            "description": "A relentless destroyer who grows stronger while wounded.",
            "bonuses": {"attack": 6, "hp": 15},
            "passive": "Bloodrage",
        },
        "warlord": {
            "name": "Warlord",
            "emoji": "📯",
            "description": "A battlefield commander with superior sustain and party leadership.",
            "bonuses": {"attack": 3, "defense": 3, "luck": 2},
            "passive": "Command",
        },
    },
    "shadow": {
        "assassin": {
            "name": "Assassin",
            "emoji": "🦂",
            "description": "A killer specializing in poison and wounded targets.",
            "bonuses": {"attack": 6, "luck": 3},
            "passive": "Deathmark",
        },
        "duelist": {
            "name": "Duelist",
            "emoji": "🤺",
            "description": "A precise combatant who excels at counters and critical chains.",
            "bonuses": {"attack": 4, "defense": 3, "luck": 2},
            "passive": "Riposte",
        },
        "trickster": {
            "name": "Trickster",
            "emoji": "🃏",
            "description": "A chaotic opportunist who bends luck and escapes danger.",
            "bonuses": {"luck": 7, "hp": 10},
            "passive": "Loaded Dice",
        },
    },
    "arcanist": {
        "elementalist": {
            "name": "Elementalist",
            "emoji": "🌩️",
            "description": "A destructive mage who amplifies burning and freezing magic.",
            "bonuses": {"attack": 7, "mana": 15},
            "passive": "Elemental Echo",
        },
        "necromancer": {
            "name": "Necromancer",
            "emoji": "🦴",
            "description": "A forbidden caster who restores life when enemies fall.",
            "bonuses": {"hp": 20, "mana": 10, "defense": 2},
            "passive": "Soul Harvest",
        },
        "chronomancer": {
            "name": "Chronomancer",
            "emoji": "⏳",
            "description": "A time-bender who manipulates cooldowns and enemy intentions.",
            "bonuses": {"mana": 20, "luck": 3},
            "passive": "Second Hand",
        },
    },
}

ABILITIES: dict[str, tuple[dict[str, Any], ...]] = {
    "vanguard": (
        {
            "key": "shield_bash",
            "name": "Shield Bash",
            "emoji": "🛡️",
            "level": 1,
            "mana": 5,
            "cooldown": 1,
            "description": "165% damage and weaken the enemy.",
        },
        {
            "key": "iron_wall",
            "name": "Iron Wall",
            "emoji": "🏰",
            "level": 4,
            "mana": 7,
            "cooldown": 3,
            "description": "Block most incoming damage and retaliate.",
        },
        {
            "key": "sunder",
            "name": "Sunder",
            "emoji": "🔨",
            "level": 7,
            "mana": 9,
            "cooldown": 3,
            "description": "Heavy damage and destroy enemy armor.",
        },
        {
            "key": "last_stand",
            "name": "Last Stand",
            "emoji": "🚩",
            "level": 12,
            "mana": 14,
            "cooldown": 5,
            "description": "Heal, guard, and strike with missing-health power.",
        },
    ),
    "shadow": (
        {
            "key": "twin_fang",
            "name": "Twin Fang",
            "emoji": "🗡️",
            "level": 1,
            "mana": 6,
            "cooldown": 1,
            "description": "Strike twice with improved critical chance.",
        },
        {
            "key": "venom_edge",
            "name": "Venom Edge",
            "emoji": "☠️",
            "level": 4,
            "mana": 7,
            "cooldown": 2,
            "description": "Damage and inflict four turns of poison.",
        },
        {
            "key": "smoke_bomb",
            "name": "Smoke Bomb",
            "emoji": "💨",
            "level": 7,
            "mana": 8,
            "cooldown": 4,
            "description": "Evade the next attack and improve your next critical.",
        },
        {
            "key": "execution",
            "name": "Execution",
            "emoji": "🦂",
            "level": 12,
            "mana": 14,
            "cooldown": 5,
            "description": "Massive damage against enemies below half health.",
        },
    ),
    "arcanist": (
        {
            "key": "arcane_lance",
            "name": "Arcane Lance",
            "emoji": "🔮",
            "level": 1,
            "mana": 8,
            "cooldown": 1,
            "description": "Powerful magic that ignores most armor.",
        },
        {
            "key": "frost_ward",
            "name": "Frost Ward",
            "emoji": "❄️",
            "level": 4,
            "mana": 9,
            "cooldown": 3,
            "description": "Gain a barrier and weaken the next enemy attack.",
        },
        {
            "key": "starfire",
            "name": "Starfire",
            "emoji": "🔥",
            "level": 7,
            "mana": 12,
            "cooldown": 3,
            "description": "Explosive damage and four turns of burning.",
        },
        {
            "key": "time_fracture",
            "name": "Time Fracture",
            "emoji": "⏳",
            "level": 12,
            "mana": 18,
            "cooldown": 6,
            "description": "Deal damage, cancel enemy intent, and reduce cooldowns.",
        },
    ),
}

TALENT_TREES: dict[str, tuple[dict[str, Any], ...]] = {
    "vanguard": (
        {"key": "unyielding", "name": "Unyielding", "max": 5, "description": "+3% maximum health per rank."},
        {"key": "weapon_mastery", "name": "Weapon Mastery", "max": 5, "description": "+2% attack per rank."},
        {"key": "retaliation", "name": "Retaliation", "max": 3, "description": "Guarding reflects damage."},
        {"key": "second_wind", "name": "Second Wind", "max": 1, "description": "Survive one fatal blow each expedition."},
    ),
    "shadow": (
        {"key": "precision", "name": "Precision", "max": 5, "description": "+2% critical chance per rank."},
        {"key": "toxicology", "name": "Toxicology", "max": 5, "description": "+10% poison damage per rank."},
        {"key": "evasion", "name": "Evasion", "max": 3, "description": "Chance to completely evade attacks."},
        {"key": "opportunist", "name": "Opportunist", "max": 1, "description": "Critical hits reduce a cooldown."},
    ),
    "arcanist": (
        {"key": "deep_reserves", "name": "Deep Reserves", "max": 5, "description": "+5% maximum mana per rank."},
        {"key": "spellpower", "name": "Spellpower", "max": 5, "description": "+3% ability damage per rank."},
        {"key": "mana_shield", "name": "Mana Shield", "max": 3, "description": "Mana absorbs part of incoming damage."},
        {"key": "overchannel", "name": "Overchannel", "max": 1, "description": "Abilities may cast without entering cooldown."},
    ),
}

ITEM_PREFIXES: tuple[dict[str, Any], ...] = (
    {"name": "Brutal", "attack": 1.22},
    {"name": "Stalwart", "defense": 1.25},
    {"name": "Vital", "hp": 1.3},
    {"name": "Fortunate", "luck": 1.35},
    {"name": "Balanced", "all": 1.12},
)

ITEM_SUFFIXES: tuple[dict[str, Any], ...] = (
    {"name": "of Embers", "effect": "burn", "description": "Critical hits may Burn."},
    {"name": "of Venom", "effect": "poison", "description": "Critical hits may Poison."},
    {"name": "of Mending", "effect": "mending", "description": "Victories restore health."},
    {"name": "of Fortune", "effect": "fortune", "description": "Find additional currency."},
    {"name": "of Warding", "effect": "warding", "description": "Take less elite damage."},
)

ITEM_SETS: dict[str, dict[str, Any]] = {
    "bulwark": {
        "name": "Lastlight Bulwark",
        "classes": ("vanguard",),
        "two": "+8 DEF",
        "three": "Guard retaliates for double damage.",
    },
    "nightstalker": {
        "name": "Nightstalker",
        "classes": ("shadow",),
        "two": "+6 LUCK",
        "three": "Critical hits extend enemy conditions.",
    },
    "starweaver": {
        "name": "Starweaver",
        "classes": ("arcanist",),
        "two": "+18 maximum mana",
        "three": "Every third ability costs no mana.",
    },
}

LEGENDARIES: tuple[dict[str, Any], ...] = (
    {
        "name": "Bellower's Silence",
        "slot": "weapon",
        "effect": "silence",
        "description": "Critical hits may cancel the enemy's intention.",
    },
    {
        "name": "Arachne's Promise",
        "slot": "charm",
        "effect": "web",
        "description": "The first enemy attack in each battle always misses.",
    },
    {
        "name": "Crown of No Kingdom",
        "slot": "armor",
        "effect": "crown",
        "description": "Gain attack and defense for every active condition.",
    },
    {
        "name": "Embermaw's Last Scale",
        "slot": "armor",
        "effect": "rebirth",
        "description": "Survive one fatal hit and erupt in flame.",
    },
    {
        "name": "The Unwritten Key",
        "slot": "charm",
        "effect": "key",
        "description": "Narrative tests roll twice and take the better result.",
    },
)

NPCS: dict[str, dict[str, Any]] = {
    "orra": {
        "name": "Orra Deepforge",
        "emoji": "⚒️",
        "role": "Smith",
        "introduction": "“Everything brought from the Deep still dreams of being down there.”",
        "quests": (
            ("A Hammer's Memory", 3, "Craft three items for Orra."),
            ("Metal That Screams", 8, "Bring Orra eight total crafting materials."),
            ("The Masterwork", 15, "Reach floor fifteen and forge a legendary-quality item."),
        ),
    },
    "mara": {
        "name": "Captain Mara Venn",
        "emoji": "🛡️",
        "role": "Contract Master",
        "introduction": "“Heroes come back with stories. Professionals come back with maps.”",
        "quests": (
            ("First Watch", 3, "Defeat three enemies."),
            ("Bounty of the Deep", 10, "Complete three contracts."),
            ("Lastlight's Champion", 20, "Defeat four bosses."),
        ),
    },
    "vesper": {
        "name": "Vesper Quill",
        "emoji": "🪶",
        "role": "Forbidden Historian",
        "introduction": "“The Deep is a sentence. Every delver is punctuation.”",
        "quests": (
            ("Ink Below", 3, "Recover three lore fragments."),
            ("The Missing Name", 7, "Recover seven lore fragments."),
            ("Read the Unwritten", 20, "Reach the Abyss Unwritten."),
        ),
    },
    "rook": {
        "name": "Rook",
        "emoji": "🎲",
        "role": "Rival Delver",
        "introduction": "“Try not to die before I beat your floor record.”",
        "quests": (
            ("Friendly Competition", 5, "Reach floor five."),
            ("No Potions", 12, "Defeat twelve enemies."),
            ("The Better Legend", 25, "Reach floor twenty-five."),
        ),
    },
}

TITLES: dict[str, tuple[str, str]] = {
    "delver": ("Delver", "Create a character."),
    "giant_killer": ("Giant Killer", "Defeat a boss."),
    "loremaster": ("Loremaster", "Recover every lore fragment."),
    "oathkeeper": ("Oathkeeper", "Complete ten contracts."),
    "riftwalker": ("Riftwalker", "Complete a challenge rift."),
    "ascendant": ("The Ascendant", "Ascend after floor twenty."),
    "hardcore": ("Deathless", "Reach floor ten in Hardcore mode."),
    "champion": ("Arena Champion", "Win ten arena duels."),
}

SCARS: tuple[str, ...] = (
    "Spiderbite Scar",
    "Cinderbrand",
    "Hollow King's Gaze",
    "Void-Touched Hand",
    "Bellower's Mark",
)

BLESSINGS: tuple[dict[str, Any], ...] = (
    {"name": "Lantern's Grace", "stat": "hp", "amount": 12},
    {"name": "Orra's Temper", "stat": "attack", "amount": 2},
    {"name": "Cartographer's Instinct", "stat": "luck", "amount": 2},
    {"name": "Silent Chapel's Ward", "stat": "defense", "amount": 2},
)

SEASON_NAMES: tuple[str, ...] = (
    "Season of the Black Lantern",
    "Season of Waking Stone",
    "Season of the Hollow Crown",
    "Season of Falling Stars",
)
