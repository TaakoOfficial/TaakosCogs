"""Static game content and pure helpers for DeepDelve."""

from __future__ import annotations

import random
from typing import Any

from .expansion_content import EXTENDED_BOSSES, EXTENDED_ENEMIES
from .loot_content import REGIONAL_BASES

GAME_CLASSES: dict[str, dict[str, Any]] = {
    "vanguard": {
        "name": "Vanguard",
        "emoji": "🛡️",
        "description": "A durable fighter who turns defense into crushing blows.",
        "max_hp": 125,
        "max_mana": 20,
        "attack": 10,
        "defense": 8,
        "luck": 3,
        "skill": "Shield Bash",
        "skill_cost": 5,
        "skill_description": "A heavy strike that deals 140% damage and weakens the enemy.",
    },
    "shadow": {
        "name": "Shadow",
        "emoji": "🗡️",
        "description": "A swift treasure hunter with deadly critical strikes.",
        "max_hp": 95,
        "max_mana": 30,
        "attack": 15,
        "defense": 4,
        "luck": 9,
        "skill": "Twin Fang",
        "skill_cost": 6,
        "skill_description": "Strike twice, with an improved chance to critically hit.",
    },
    "arcanist": {
        "name": "Arcanist",
        "emoji": "🔮",
        "description": "A fragile spellcaster whose magic cuts through armor.",
        "max_hp": 82,
        "max_mana": 48,
        "attack": 18,
        "defense": 3,
        "luck": 5,
        "skill": "Arcane Lance",
        "skill_cost": 8,
        "skill_description": "Deal powerful damage that ignores most enemy defense.",
    },
}

ENEMIES: tuple[dict[str, Any], ...] = (
    {"name": "Cave Rat", "emoji": "🐀", "tier": 1, "hp": 30, "attack": 7, "defense": 1, "gold": 8, "xp": 11},
    {"name": "Tunnel Slime", "emoji": "🟢", "tier": 1, "hp": 38, "attack": 6, "defense": 2, "gold": 9, "xp": 12},
    {"name": "Restless Bones", "emoji": "💀", "tier": 1, "hp": 42, "attack": 8, "defense": 2, "gold": 11, "xp": 14},
    {"name": "Goblin Looter", "emoji": "👺", "tier": 1, "hp": 45, "attack": 9, "defense": 3, "gold": 13, "xp": 15},
    {"name": "Crypt Spider", "emoji": "🕷️", "tier": 2, "hp": 55, "attack": 11, "defense": 3, "gold": 16, "xp": 19},
    {"name": "Fungal Brute", "emoji": "🍄", "tier": 2, "hp": 65, "attack": 12, "defense": 5, "gold": 18, "xp": 22},
    {"name": "Grave Robber", "emoji": "🥷", "tier": 2, "hp": 61, "attack": 14, "defense": 4, "gold": 22, "xp": 24},
    {"name": "Stone Gargoyle", "emoji": "🗿", "tier": 2, "hp": 78, "attack": 13, "defense": 8, "gold": 24, "xp": 27},
    {"name": "Ash Wraith", "emoji": "👻", "tier": 3, "hp": 82, "attack": 17, "defense": 6, "gold": 29, "xp": 32},
    {"name": "Minotaur Exile", "emoji": "🐂", "tier": 3, "hp": 105, "attack": 18, "defense": 8, "gold": 34, "xp": 37},
    {"name": "Cult Magus", "emoji": "🧙", "tier": 3, "hp": 90, "attack": 21, "defense": 5, "gold": 38, "xp": 40},
    {"name": "Iron Devourer", "emoji": "⚙️", "tier": 3, "hp": 120, "attack": 19, "defense": 11, "gold": 42, "xp": 44},
    {"name": "Void Stalker", "emoji": "🌑", "tier": 4, "hp": 128, "attack": 23, "defense": 9, "gold": 48, "xp": 51},
    {"name": "Magma Elemental", "emoji": "🔥", "tier": 4, "hp": 145, "attack": 25, "defense": 12, "gold": 54, "xp": 58},
    {"name": "Fallen Champion", "emoji": "⚔️", "tier": 4, "hp": 155, "attack": 27, "defense": 13, "gold": 62, "xp": 64},
    {"name": "Abyssal Horror", "emoji": "🐙", "tier": 4, "hp": 175, "attack": 29, "defense": 11, "gold": 70, "xp": 72},
) + EXTENDED_ENEMIES

BOSSES: tuple[dict[str, Any], ...] = (
    {
        "name": "The Bellower",
        "emoji": "👹",
        "description": "Its roar shakes loose stones from the ceiling.",
        "hp": 155,
        "attack": 16,
        "defense": 7,
        "gold": 100,
        "xp": 110,
    },
    {
        "name": "Queen Arachne",
        "emoji": "🕸️",
        "description": "The webbed throne room trembles beneath eight armored legs.",
        "hp": 245,
        "attack": 23,
        "defense": 10,
        "gold": 190,
        "xp": 200,
    },
    {
        "name": "The Hollow King",
        "emoji": "👑",
        "description": "A dead monarch raises a blade made from pure shadow.",
        "hp": 350,
        "attack": 31,
        "defense": 15,
        "gold": 320,
        "xp": 330,
    },
    {
        "name": "Embermaw",
        "emoji": "🐉",
        "description": "Ancient scales glow like a furnace beneath the mountain.",
        "hp": 490,
        "attack": 39,
        "defense": 19,
        "gold": 500,
        "xp": 520,
    },
) + EXTENDED_BOSSES

ROOM_TEXTS: tuple[str, ...] = (
    "Torchlight reveals a chamber scratched with forgotten names.",
    "Cold air spills from a passage that should not exist.",
    "Broken weapons litter the floor like warnings.",
    "Something moves just beyond the edge of your light.",
    "A distant bell tolls once, deep beneath the stone.",
    "Blue moss illuminates a stairway worn smooth by centuries.",
    "The corridor opens into the ruins of an underground chapel.",
    "You follow wet footprints that abruptly stop at a wall.",
    "Whispers echo from a cracked well in the center of the room.",
    "An old campsite still smolders, but its owner is nowhere nearby.",
)

RARITIES: tuple[dict[str, Any], ...] = (
    {"name": "Common", "emoji": "⚪", "multiplier": 1.0, "color": 0x95A5A6},
    {"name": "Uncommon", "emoji": "🟢", "multiplier": 1.3, "color": 0x2ECC71},
    {"name": "Rare", "emoji": "🔵", "multiplier": 1.7, "color": 0x3498DB},
    {"name": "Epic", "emoji": "🟣", "multiplier": 2.25, "color": 0x9B59B6},
    {"name": "Legendary", "emoji": "🟠", "multiplier": 3.0, "color": 0xF39C12},
)

ITEM_NAMES: dict[str, tuple[tuple[str, str], ...]] = {
    "weapon": (
        ("Rusty", "Shortsword"),
        ("Goblin", "Cleaver"),
        ("Moonlit", "Dagger"),
        ("Runed", "Warhammer"),
        ("Ashen", "Staff"),
        ("Royal", "Halberd"),
        ("Voidforged", "Blade"),
    ),
    "armor": (
        ("Patched", "Leathers"),
        ("Iron", "Cuirass"),
        ("Spidersilk", "Mail"),
        ("Runed", "Plate"),
        ("Emberwoven", "Robes"),
        ("Royal", "Bulwark"),
        ("Abyssal", "Carapace"),
    ),
    "charm": (
        ("Cracked", "Idol"),
        ("Lucky", "Coin"),
        ("Whispering", "Locket"),
        ("Runed", "Talisman"),
        ("Dragonbone", "Charm"),
        ("Royal", "Signet"),
        ("Starless", "Eye"),
    ),
}

ACHIEVEMENTS: dict[str, dict[str, Any]] = {
    "first_blood": {"name": "First Blood", "description": "Defeat your first enemy.", "gold": 25},
    "delver_five": {"name": "Into the Dark", "description": "Reach floor 5.", "gold": 75},
    "boss_slayer": {"name": "Giant Killer", "description": "Defeat your first boss.", "gold": 150},
    "wealthy": {"name": "Heavy Pockets", "description": "Hold 1,000 gold.", "gold": 100},
    "veteran": {"name": "Dungeon Veteran", "description": "Defeat 100 enemies.", "gold": 250},
    "deep_twenty": {"name": "No Light Remains", "description": "Reach floor 20.", "gold": 500},
    "contractor": {"name": "Oathkeeper", "description": "Complete your first contract.", "gold": 100},
    "lorekeeper": {"name": "Whispers Remembered", "description": "Recover five lore fragments.", "gold": 175},
    "master_smith": {"name": "Made in Darkness", "description": "Craft ten pieces of equipment.", "gold": 300},
    "riddlemaster": {"name": "Doors of the Mind", "description": "Solve five unique dungeon puzzles.", "gold": 350},
    "bonded": {"name": "Never Delve Alone", "description": "Raise a companion to bond 50.", "gold": 300},
    "professional": {"name": "A Life Below", "description": "Reach profession level 10.", "gold": 400},
    "chronicler": {"name": "The Final Word", "description": "Complete the first campaign.", "gold": 750},
}

REGIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "The Forgotten Warrens",
        "floors": "1–5",
        "emoji": "🕯️",
        "color": 0x6C5B7B,
        "description": "Collapsed cellars and burial tunnels beneath Lastlight.",
        "rooms": (
            "Roots push through the ceiling like grasping fingers.",
            "Names carved into the bricks have been violently scratched away.",
            "A rusted mine cart rolls past on its own, wheels screaming.",
            "Wax figures kneel around a cold and empty lantern.",
        ),
        "material": "iron",
    },
    {
        "name": "The Verdant Crypt",
        "floors": "6–10",
        "emoji": "🌿",
        "color": 0x1E8449,
        "description": "A drowned necropolis reclaimed by luminous fungus and thorn.",
        "rooms": (
            "Bioluminescent spores drift through the air like green snow.",
            "A stone coffin has split open beneath the roots of a pale tree.",
            "Black water reflects a sky filled with unfamiliar stars.",
            "Flowers bloom in the footprints you leave behind.",
        ),
        "material": "silk",
    },
    {
        "name": "The Cinder Foundry",
        "floors": "11–15",
        "emoji": "🔥",
        "color": 0xBA4A00,
        "description": "An impossible forge whose machines still serve vanished masters.",
        "rooms": (
            "Chains move through the ceiling, hauling unseen burdens upward.",
            "Molten metal runs through channels cut into the black floor.",
            "A hammer the size of a house strikes somewhere beyond the wall.",
            "Empty suits of armor turn their helmets to follow you.",
        ),
        "material": "ember",
    },
    {
        "name": "The Starless Court",
        "floors": "16–20",
        "emoji": "🌑",
        "color": 0x17202A,
        "description": "The ruined palace of a kingdom erased from every history.",
        "rooms": (
            "Tattered banners depict a crown surrounding a black sun.",
            "Ghostly courtiers continue a dance without music.",
            "A banquet table is laid with food that turns to ash when touched.",
            "Your reflection in a silver mirror bows before you do.",
        ),
        "material": "essence",
    },
    {
        "name": "The Abyss Unwritten",
        "floors": "21+",
        "emoji": "🌀",
        "color": 0x4A235A,
        "description": "Reality frays where the dungeon begins dreaming of itself.",
        "rooms": (
            "The corridor folds upward and continues across the ceiling.",
            "A door opens onto the room you just left, but something is different.",
            "Constellations pulse beneath the transparent stone floor.",
            "For one breath, you remember dying here centuries ago.",
        ),
        "material": "voidglass",
    },
)

LORE_FRAGMENTS: tuple[dict[str, str], ...] = (
    {
        "title": "The First Descent",
        "text": "Lastlight was not built above the Deep. It was built to keep something below it.",
    },
    {
        "title": "The Nameless Surveyor",
        "text": "Every map disagrees with the last. The dungeon rearranges itself when no living eye watches.",
    },
    {
        "title": "The Lantern Oath",
        "text": "The first delvers carried blue flame. When the final lantern dies, the sealed stair will open upward.",
    },
    {
        "title": "A Queen in Silk",
        "text": "Arachne was once the court astronomer. She learned that the stars beneath the earth were eggs.",
    },
    {
        "title": "The Hollow Crown",
        "text": "The king removed his own name from history so the thing wearing his face could never escape.",
    },
    {
        "title": "Foundry Directive",
        "text": "Forge bodies without souls. The Court has an excess of souls and a shortage of loyal bodies.",
    },
    {
        "title": "The Fifth Bell",
        "text": "Four bells warn the city. The fifth is not a warning; it is an invitation.",
    },
    {
        "title": "Embermaw's Bargain",
        "text": "The dragon does not guard the treasure. The treasure is payment for guarding us.",
    },
    {
        "title": "The Starless Court",
        "text": "Their sun did not die. It looked down, saw the Deep looking back, and fled.",
    },
    {
        "title": "Margin of the World",
        "text": "Past the twentieth floor, write nothing down. Words become doors, and readers become keys.",
    },
    {
        "title": "The Surveyor's Last Map",
        "text": "The red route marks where I walked. The blue route marks where the dungeon remembers I walked.",
    },
    {
        "title": "Spore Gospel",
        "text": "We are not the first life to grow upon these graves. We are merely the first to call decay an ending.",
    },
    {
        "title": "Inventory of Borrowed Lives",
        "text": "Three kings, eleven soldiers, a baker, and one frightened child were pressed into the same iron body.",
    },
    {
        "title": "Letter Never Sent",
        "text": "Mara, the fifth bell is beneath your office. You have stood guard over it every day without knowing.",
    },
    {
        "title": "The Star That Begged",
        "text": "Do not return me to the sky. It is colder there than your stories say, and something has eaten my sisters.",
    },
    {
        "title": "Rook's Real Name",
        "text": "The rival crossed out every line except this one: I joke because the Deep listens when I am afraid.",
    },
    {
        "title": "Orra's First Hammer",
        "text": "A tool becomes sacred after it has made something its maker could not destroy.",
    },
    {
        "title": "The Unremembered Saint",
        "text": "Caligo performed one miracle: she convinced history that the coming darkness had never seen the light.",
    },
    {
        "title": "A Future Obituary",
        "text": "Lastlight survived the opening of the Deep. No living witness could agree who opened it.",
    },
    {
        "title": "The Author's Dedication",
        "text": "For the one who reaches the final page: you were always my favorite character.",
    },
)

MATERIALS: dict[str, dict[str, str]] = {
    "iron": {"name": "Warren Iron", "emoji": "⛓️"},
    "silk": {"name": "Crypt Silk", "emoji": "🕸️"},
    "ember": {"name": "Living Ember", "emoji": "🔥"},
    "essence": {"name": "Royal Essence", "emoji": "👑"},
    "voidglass": {"name": "Voidglass", "emoji": "🔷"},
}

AFFIXES: tuple[dict[str, Any], ...] = (
    {"name": "Armored", "emoji": "🛡️", "defense": 1.35, "attack": 1.0, "hp": 1.15, "effect": ""},
    {"name": "Frenzied", "emoji": "💢", "defense": 0.9, "attack": 1.35, "hp": 0.95, "effect": ""},
    {"name": "Venomous", "emoji": "☠️", "defense": 1.0, "attack": 1.05, "hp": 1.0, "effect": "poison"},
    {"name": "Vampiric", "emoji": "🩸", "defense": 1.0, "attack": 1.1, "hp": 1.1, "effect": "drain"},
    {"name": "Ancient", "emoji": "✨", "defense": 1.2, "attack": 1.2, "hp": 1.3, "effect": ""},
)

CHOICES: tuple[dict[str, Any], ...] = (
    {
        "key": "sealed_door",
        "title": "The Sealed Door",
        "emoji": "🚪",
        "text": "A bronze door bears three locks and a warning written in fresh blood.",
        "options": (
            ("force", "Force It", "⚔️"),
            ("study", "Study the Runes", "🔮"),
            ("leave", "Walk Away", "↩️"),
        ),
    },
    {
        "key": "dark_altar",
        "title": "The Dark Altar",
        "emoji": "🩸",
        "text": "A black altar promises strength in a voice that sounds exactly like yours.",
        "options": (
            ("offer", "Make an Offering", "🪙"),
            ("destroy", "Destroy It", "💥"),
            ("leave", "Refuse", "↩️"),
        ),
    },
    {
        "key": "lost_delver",
        "title": "The Lost Delver",
        "emoji": "🧑‍🦯",
        "text": "An injured explorer begs for help while something scratches inside the walls.",
        "options": (
            ("aid", "Give a Potion", "🧪"),
            ("escort", "Escort Them", "🛡️"),
            ("leave", "Move On", "↩️"),
        ),
    },
    {
        "key": "weeping_sword",
        "title": "The Weeping Sword",
        "emoji": "🗡️",
        "text": "A sword embedded in the wall weeps clear water and asks you to remember its final wielder.",
        "options": (
            ("study", "Hear Its Memory", "🧠"),
            ("force", "Pull It Free", "💪"),
            ("leave", "Leave It Mourning", "↩️"),
        ),
    },
    {
        "key": "fungal_feast",
        "title": "The Feast That Breathes",
        "emoji": "🍄",
        "text": "A table of luminous mushrooms exhales in unison. One place has been set for you.",
        "options": (
            ("aid", "Taste the Feast", "🍽️"),
            ("destroy", "Burn the Table", "🔥"),
            ("leave", "Decline Politely", "↩️"),
        ),
    },
    {
        "key": "clockwork_child",
        "title": "The Clockwork Child",
        "emoji": "🤖",
        "text": "A small brass figure asks whether it is alive, holding a key shaped like a human heartbeat.",
        "options": (
            ("aid", "Wind the Key", "🗝️"),
            ("study", "Examine the Mechanism", "🔎"),
            ("leave", "Say Nothing", "↩️"),
        ),
    },
    {
        "key": "empty_throne",
        "title": "The Empty Throne",
        "emoji": "🪑",
        "text": "The throne is empty, yet every ghost in the hall bows when you approach it.",
        "options": (
            ("offer", "Kneel", "👑"),
            ("destroy", "Shatter the Throne", "💥"),
            ("leave", "Refuse the Court", "↩️"),
        ),
    },
    {
        "key": "future_grave",
        "title": "Your Future Grave",
        "emoji": "🪦",
        "text": "A gravestone bears your name, tomorrow's date, and a cause of death scratched away.",
        "options": (
            ("study", "Read the Hidden Words", "📖"),
            ("destroy", "Break the Stone", "🔨"),
            ("leave", "Walk Past", "↩️"),
        ),
    },
    {
        "key": "lastlight_camp",
        "title": "The Impossible Camp",
        "emoji": "🏕️",
        "text": "A Lastlight campfire burns where no expedition should be. Three bedrolls wait, but only yours has a shadow.",
        "options": (
            ("rest", "Rest by the Fire", "🔥"),
            ("study", "Read the Field Notes", "📚"),
            ("prepare", "Search the Supplies", "🎒"),
        ),
    },
    {
        "key": "judgment_mirror",
        "title": "The Mirror of Judgment",
        "emoji": "🪞",
        "text": (
            "A silver mirror contains every cruel and compassionate choice you refused to make. "
            "Your reflection asks which version of you deserves to leave."
        ),
        "options": (
            ("absolve", "Release the Prisoners", "☀️"),
            ("bargain", "Negotiate a Truth", "⚖️"),
            ("consume", "Devour Their Sins", "🌑"),
        ),
    },
)


def region_for_floor(floor: int) -> dict[str, Any]:
    """Return the authored region containing a floor."""
    index = min(len(REGIONS) - 1, max(0, (max(1, floor) - 1) // 5))
    return REGIONS[index]


def apply_affix(enemy: dict[str, Any], floor: int, rng: random.Random = random) -> dict[str, Any]:
    """Occasionally turn a normal enemy into an elite."""
    chance = min(0.35, 0.08 + max(0, floor - 1) * 0.008)
    if enemy.get("boss") or rng.random() >= chance:
        enemy["affix"] = {}
        return enemy
    affix = dict(rng.choice(AFFIXES))
    enemy.setdefault("base_name", enemy["name"])
    enemy.setdefault("codex_key", f"creature:{enemy['base_name'].lower().replace(' ', '_')}")
    enemy["name"] = f"{affix['name']} {enemy['name']}"
    enemy["emoji"] = affix["emoji"]
    for field in ("hp", "attack", "defense"):
        endurance = max(1.25, 1.5 - max(0, floor - 1) * 0.01) if field == "hp" else 1.0
        enemy[field] = max(1, round(enemy[field] * affix[field] * endurance))
    enemy["max_hp"] = enemy["hp"]
    enemy["gold"] = round(enemy["gold"] * 1.5)
    enemy["xp"] = round(enemy["xp"] * 1.4)
    enemy["affix"] = affix
    return enemy


def xp_for_level(level: int) -> int:
    """Return the experience required to advance from ``level``."""
    return 80 + (max(1, level) - 1) * 45


def enemy_for_floor(floor: int, rng: random.Random = random) -> dict[str, Any]:
    """Build a scaled random enemy suitable for a floor."""
    tier = min(5, max(1, (max(1, floor) - 1) // 5 + 1))
    choices = [enemy for enemy in ENEMIES if enemy["tier"] in {tier, max(1, tier - 1)}]
    base = dict(rng.choice(choices))
    scale = 1 + max(0, floor - 1) * 0.085
    variance = rng.uniform(0.92, 1.08)
    for field in ("hp", "attack", "defense"):
        multiplier = max(2.4, 2.85 - max(1, floor) * 0.012) if field == "hp" else 1.0
        base[field] = max(1, round(base[field] * scale * variance * multiplier))
    base["gold"] = max(1, round(base["gold"] * (1 + max(0, floor - 1) * 0.045) * variance))
    base["xp"] = max(1, round(base["xp"] * (1 + max(0, floor - 1) * 0.07) * variance))
    base.update(
        {
            "max_hp": base["hp"],
            "boss": False,
            "floor": floor,
            "weakened": 0,
            "base_name": base["name"],
            "codex_key": f"creature:{base['name'].lower().replace(' ', '_')}",
        },
    )
    return base


def boss_for_floor(floor: int) -> dict[str, Any]:
    """Build a boss on a monotonic curve beyond the authored encounters."""
    boss_number = max(1, floor // 5)
    identity = dict(BOSSES[(boss_number - 1) % len(BOSSES)])
    identity_name = identity["name"]
    if boss_number <= len(BOSSES):
        base = identity
    else:
        steps = boss_number - len(BOSSES)
        anchor = BOSSES[-1]
        base = identity
        scales = {
            "hp": 1 + steps * 0.32,
            "attack": 1 + steps * 0.16,
            "defense": 1 + steps * 0.12,
            "gold": 1 + steps * 0.16,
            "xp": 1 + steps * 0.15,
        }
        for field, scale in scales.items():
            base[field] = max(int(anchor[field]) + 1, round(int(anchor[field]) * scale))
        base["name"] = f"Ascended {base['name']}"
    boss_endurance = max(3.5, 3.9 - max(0, floor - 5) * 0.012)
    base["hp"] = round(int(base["hp"]) * boss_endurance)
    base["attack"] = round(int(base["attack"]) * 1.4)
    base.update(
        {
            "max_hp": base["hp"],
            "boss": True,
            "floor": floor,
            "weakened": 0,
            "base_name": identity_name,
            "codex_key": f"boss:{identity_name.lower().replace(' ', '_')}",
        },
    )
    return base


def roll_rarity(floor: int, luck: int, rng: random.Random = random) -> int:
    """Roll a rarity index with modest floor and luck improvements."""
    legendary = min(5.0, 0.35 + floor * 0.06 + luck * 0.035)
    epic = min(12.0, 2.0 + floor * 0.12 + luck * 0.07)
    rare = min(25.0, 8.0 + floor * 0.18 + luck * 0.12)
    uncommon = min(42.0, 26.0 + floor * 0.2 + luck * 0.15)
    roll = rng.uniform(0, 100)
    if roll < legendary:
        return 4
    if roll < legendary + epic:
        return 3
    if roll < legendary + epic + rare:
        return 2
    if roll < legendary + epic + rare + uncommon:
        return 1
    return 0


def generate_item(
    floor: int,
    luck: int,
    rng: random.Random = random,
    slot: str | None = None,
    rarity_index: int | None = None,
) -> dict[str, Any]:
    """Generate a serializable equipment item."""
    if slot not in {"weapon", "armor", "charm"}:
        slot = rng.choice(("weapon", "armor", "charm"))
    rarity_index = roll_rarity(floor, luck, rng) if rarity_index is None else max(0, min(4, rarity_index))
    rarity = RARITIES[rarity_index]
    region_index = min(len(REGIONAL_BASES) - 1, max(0, (max(1, floor) - 1) // 5))
    noun = rng.choice(REGIONAL_BASES[region_index][slot])
    prefix = ("Worn", "Tempered", "Runed", "Exalted", "Mythic")[rarity_index]
    value = round((12 + floor * 7) * rarity["multiplier"])
    primary = max(1, round((2 + floor * 0.65) * rarity["multiplier"]))
    item = {
        "id": f"{rng.randrange(16**8):08x}",
        "name": f"{prefix} {noun}",
        "slot": slot,
        "rarity": rarity["name"],
        "rarity_index": rarity_index,
        "attack": 0,
        "defense": 0,
        "hp": 0,
        "luck": 0,
        "value": value,
        "floor": floor,
    }
    if slot == "weapon":
        item["attack"] = primary
        item["luck"] = rarity_index // 2
    elif slot == "armor":
        item["defense"] = primary
        item["hp"] = round(primary * 2.5)
    else:
        item["luck"] = max(1, round(primary * 0.6))
        item[rng.choice(("attack", "defense", "hp"))] += max(1, round(primary * 0.55))
    return item


def item_stat_line(item: dict[str, Any]) -> str:
    """Return a compact equipment stat description."""
    stats = []
    for key, label in (("attack", "ATK"), ("defense", "DEF"), ("hp", "HP"), ("luck", "LUCK")):
        if item.get(key):
            stats.append(f"+{item[key]} {label}")
    return " • ".join(stats) or "No bonuses"
