"""Authored content for DeepDelve's solo chronicle expansion."""

from __future__ import annotations

from typing import Any

CAMPAIGN_CHAPTERS: tuple[dict[str, Any], ...] = (
    {
        "key": "lantern_below",
        "number": 1,
        "name": "The Lantern Below",
        "emoji": "🏮",
        "floor": 1,
        "summary": "A dead delver arrives at Lastlight carrying a lantern that still whispers your name.",
        "scenes": (
            "At Lastlight's gate, the corpse of a missing surveyor grips a blue lantern. "
            "Its flame leans toward you despite the wind.",
            "Vesper identifies the lantern as one carried during the First Descent. Its base hides a map drawn in fresh ink.",
            "Beneath the Warrens, the map leads to a sealed watchroom. A voice behind the door asks "
            "whether Lastlight deserves the truth.",
        ),
        "choice": {
            "prompt": "What will guide your first descent?",
            "options": {
                "truth": ("Tell Lastlight everything", "Honesty opens allies—and dangerous attention."),
                "mercy": ("Hide the worst of it", "You protect the town, but carry the secret alone."),
                "power": ("Keep the lantern", "The flame answers ambition with a hungry warmth."),
            },
        },
        "reward": {"gold": 125, "xp": 90, "tokens": 1},
    },
    {
        "key": "silken_sky",
        "number": 2,
        "name": "The Silken Sky",
        "emoji": "🕸️",
        "floor": 6,
        "summary": "The stars beneath the Verdant Crypt begin to hatch.",
        "scenes": (
            "Black water shows constellations that do not exist above. One star blinks when you do.",
            "Orra forges a lens from crypt silk. Through it, every strand in Arachne's kingdom forms a map of Lastlight.",
            "In the drowned observatory, an unhatched star begs you not to return it to the sky.",
        ),
        "choice": {
            "prompt": "Decide the fate of the fallen star.",
            "options": {
                "free": ("Free the star", "Compassion may create a strange ally."),
                "seal": ("Seal it forever", "Lastlight's safety comes before unknowable life."),
                "harvest": ("Claim its fire", "Power taken from heaven always leaves a shadow."),
            },
        },
        "reward": {"gold": 250, "xp": 175, "tokens": 1},
    },
    {
        "key": "iron_dream",
        "number": 3,
        "name": "The Iron Dream",
        "emoji": "⚙️",
        "floor": 11,
        "summary": "The Cinder Foundry is manufacturing people who remember lives they never lived.",
        "scenes": (
            "An empty suit of armor calls you by a childhood name no one in Lastlight knows.",
            "The Foundry's memory press contains thousands of stolen lives, each stamped onto a metal leaf.",
            "Its ancient overseer offers to rebuild everyone the Deep has taken—if you restart the furnaces.",
        ),
        "choice": {
            "prompt": "What becomes of the memory forge?",
            "options": {
                "destroy": ("Break the press", "The dead remain dead, and their memories remain their own."),
                "preserve": ("Preserve the archive", "Knowledge survives, watched by those who fear it."),
                "ignite": ("Restart the forge", "Lastlight gains miracles made from stolen identity."),
            },
        },
        "reward": {"gold": 400, "xp": 280, "tokens": 2},
    },
    {
        "key": "hollow_name",
        "number": 4,
        "name": "The Hollow Name",
        "emoji": "👑",
        "floor": 16,
        "summary": "The Hollow King did not lose his name. He hid it inside Lastlight's oldest family.",
        "scenes": (
            "Every portrait in the Starless Court changes overnight to show your face beneath its crown.",
            "Rook discovers the royal bloodline survived above. The final heir has guarded Lastlight all along.",
            "At the black throne, the King's true name waits to be spoken, erased, or inherited.",
        ),
        "choice": {
            "prompt": "Finish the reign of the Hollow King.",
            "options": {
                "speak": ("Speak the true name", "Memory returns to the kingdom, including every crime."),
                "erase": ("Erase it forever", "The curse ends at the cost of a history no one can recover."),
                "inherit": ("Take the name", "You bind the crown to a living will—your own."),
            },
        },
        "reward": {"gold": 650, "xp": 425, "tokens": 2},
    },
    {
        "key": "fifth_bell",
        "number": 5,
        "name": "When the Fifth Bell Rings",
        "emoji": "🔔",
        "floor": 20,
        "summary": "The final warning bell sounds from beneath Lastlight, and the city answers.",
        "scenes": (
            "Four bells toll above. A fifth answers from far below, and every locked door in Lastlight opens.",
            "The Deep was never a prison under the city. Lastlight is the lock built inside the prison.",
            "At the Margin of the World, the architect of the dungeon offers one last bargain: descend, "
            "seal the way, or let the world learn what waits beneath it.",
        ),
        "choice": {
            "prompt": "Write the ending of the First Chronicle.",
            "options": {
                "descend": ("Become the Last Delver", "You pursue the source beyond every authored floor."),
                "seal": ("Become the Warden", "You bind the Deep and accept the burden of guarding it."),
                "reveal": ("Open the truth", "The age of solitary delvers ends; the world must choose together."),
            },
        },
        "reward": {"gold": 1000, "xp": 700, "tokens": 3},
    },
)

PUZZLES: tuple[dict[str, Any], ...] = (
    {
        "key": "three_statues",
        "name": "The Three Watchers",
        "emoji": "🗿",
        "min_floor": 1,
        "max_floor": 5,
        "text": (
            "Three statues face east, south, and west. A plaque reads: "
            "“I wake where the day is born, die where it is buried, and never look upon midnight.”"
        ),
        "options": {"east": "Turn the east statue", "south": "Turn the south statue", "west": "Turn the west statue"},
        "answer": "east",
        "success": "At sunrise",
        "hint": "The answer is a direction associated with sunrise.",
    },
    {
        "key": "mushroom_chorus",
        "name": "The Spore Choir",
        "emoji": "🍄",
        "min_floor": 6,
        "max_floor": 10,
        "text": ("Four caps sing in a loop: blue, red, violet, blue, red… Only the next voice will open the root-bound gate."),
        "options": {"blue": "Touch blue", "red": "Touch red", "violet": "Touch violet"},
        "answer": "violet",
        "success": "The third voice",
        "hint": "Listen for a repeating sequence of three.",
    },
    {
        "key": "foundry_weight",
        "name": "The Foundry Balance",
        "emoji": "⚖️",
        "min_floor": 11,
        "max_floor": 15,
        "text": (
            "A brass scale holds two iron ingots and one ember on the left. "
            "The right holds one ingot and three embers. It balances. Which weighs more?"
        ),
        "options": {"iron": "An iron ingot", "ember": "A living ember", "equal": "They are equal"},
        "answer": "ember",
        "success": "The living ember",
        "hint": "Remove one ingot and one ember from both sides, then compare what remains.",
    },
    {
        "key": "mirror_court",
        "name": "The Courtiers' Mirrors",
        "emoji": "🪞",
        "min_floor": 16,
        "max_floor": 20,
        "text": (
            "One mirror always lies, one always tells the truth, and one repeats your belief. "
            "The truthful mirror says, “The silver door is safe.” Which door do you take?"
        ),
        "options": {"silver": "The silver door", "black": "The black door", "mirror": "Step through the mirror"},
        "answer": "silver",
        "success": "Trust the known truth",
        "hint": "You have already been told which speaker is truthful.",
    },
    {
        "key": "unwritten_word",
        "name": "A Word Without Letters",
        "emoji": "🌀",
        "min_floor": 21,
        "max_floor": 999,
        "text": ("A door asks: “What becomes larger the more you remove from it?” Three answers form in the air."),
        "options": {"wound": "A wound", "hole": "A hole", "memory": "A memory"},
        "answer": "hole",
        "success": "A hole",
        "hint": "Think of empty space created by taking material away.",
    },
)

COMPANIONS: dict[str, dict[str, Any]] = {
    "brindle": {
        "name": "Brindle",
        "emoji": "🐕",
        "role": "Warren Hound",
        "unlock_floor": 3,
        "description": "A scarred tunnel hound who finds traps before they find you.",
        "passive": "10% trap avoidance and improved material finds.",
        "bond_lines": (
            "Brindle watches every dark passage, but keeps one ear turned toward you.",
            "Brindle has learned the sound of your fear and quietly stands closer.",
            "No path is too dark while Brindle can still find your trail home.",
        ),
        "attack": 3,
        "defense": 0,
        "luck": 2,
    },
    "mote": {
        "name": "Mote",
        "emoji": "🧚",
        "role": "Spore Wisp",
        "unlock_floor": 8,
        "description": "A glowing mote born from a fallen star's dream.",
        "passive": "Restores mana after battle and improves puzzle rewards.",
        "bond_lines": (
            "Mote imitates the rhythm of your lantern with shy pulses of light.",
            "Mote paints tiny constellations in the air whenever you make camp.",
            "Mote no longer calls the sky home. Home is wherever your lantern stops.",
        ),
        "attack": 2,
        "defense": 0,
        "luck": 3,
    },
    "clank": {
        "name": "Clank",
        "emoji": "🤖",
        "role": "Memory Automaton",
        "unlock_floor": 13,
        "description": "A tiny foundry construct with the manners of a forgotten knight.",
        "passive": "Adds defense and occasionally finds extra crafting materials.",
        "bond_lines": (
            "Clank salutes before every door, including doors you just exited.",
            "Clank remembers fragments of knighthood and insists on polishing your armor.",
            "Clank has recovered one complete memory: choosing to follow you.",
        ),
        "attack": 1,
        "defense": 3,
        "luck": 0,
    },
    "nocturne": {
        "name": "Nocturne",
        "emoji": "🦇",
        "role": "Court Familiar",
        "unlock_floor": 18,
        "description": "A royal bat who insists it is merely between kingdoms.",
        "passive": "Improves critical chance and softens elite enemies.",
        "bond_lines": (
            "Nocturne claims your shoulder is merely a strategically superior perch.",
            "Nocturne has begun referring to your camp as the temporary royal court.",
            "Nocturne offers you its broken crown. Apparently the abdication is permanent.",
        ),
        "attack": 3,
        "defense": 1,
        "luck": 2,
    },
    "echo": {
        "name": "Echo",
        "emoji": "🌌",
        "role": "Unwritten Shade",
        "unlock_floor": 23,
        "description": "Your shadow from a future expedition that never happened.",
        "passive": "Amplifies all stats and sometimes preserves an exploration turn.",
        "bond_lines": (
            "Echo moves a heartbeat before you do, then pretends not to notice.",
            "Echo remembers victories you have not achieved and mourns deaths you avoided.",
            "For the first time, Echo casts a shadow of its own beside yours.",
        ),
        "attack": 3,
        "defense": 2,
        "luck": 3,
    },
}

PROFESSIONS: dict[str, dict[str, Any]] = {
    "blacksmith": {
        "name": "Blacksmith",
        "emoji": "⚒️",
        "description": "Master equipment, upgrades, and the tempering of impossible metals.",
        "benefit": "Cheaper crafting; crafted items gain bonus upgrade levels.",
    },
    "alchemist": {
        "name": "Alchemist",
        "emoji": "⚗️",
        "description": "Distill dungeon matter into potions, tonics, and volatile solutions.",
        "benefit": "Cheaper potions; chance to brew a bonus potion after gathering.",
    },
    "cartographer": {
        "name": "Cartographer",
        "emoji": "🗺️",
        "description": "Read the Deep's shifting geometry and record paths that should not exist.",
        "benefit": "More daily turns; increased puzzle and exploration rewards.",
    },
    "relic_hunter": {
        "name": "Relic Hunter",
        "emoji": "🏺",
        "description": "Recover, identify, and profit from the artifacts of vanished civilizations.",
        "benefit": "Better treasure rarity and additional arcane shards.",
    },
}

TOWN_BUILDINGS: dict[str, dict[str, Any]] = {
    "forge": {
        "name": "Deepforge",
        "emoji": "⚒️",
        "description": "Reduces crafting costs and improves crafted equipment.",
        "costs": (500, 1400, 3200, 7000),
    },
    "infirmary": {
        "name": "Lantern Infirmary",
        "emoji": "🏥",
        "description": "Reduces rest prices and strengthens healing potions.",
        "costs": (450, 1250, 2900, 6500),
    },
    "archive": {
        "name": "Forbidden Archive",
        "emoji": "📚",
        "description": "Improves lore, puzzle, and campaign rewards.",
        "costs": (600, 1600, 3600, 8000),
    },
    "watch": {
        "name": "Lastlight Watch",
        "emoji": "🛡️",
        "description": "Weakens dangerous events and grants more daily turns.",
        "costs": (550, 1500, 3400, 7600),
    },
}

WORLD_EVENTS: tuple[dict[str, Any], ...] = (
    {
        "key": "black_rain",
        "name": "The Black Rain",
        "emoji": "🌧️",
        "description": "Ink-dark rain falls upward from the dungeon. Enemies grow fierce, but leave richer spoils.",
        "combat": 1.15,
        "reward": 1.35,
        "puzzle": 1.0,
    },
    {
        "key": "lantern_festival",
        "name": "Festival of Last Light",
        "emoji": "🏮",
        "description": "The outpost burns a thousand blue lanterns. Services are cheaper and spirits run high.",
        "combat": 0.95,
        "reward": 1.1,
        "puzzle": 1.1,
    },
    {
        "key": "shifting_stairs",
        "name": "The Shifting Stairs",
        "emoji": "🪜",
        "description": "Passages rearrange by the hour, exposing puzzles and forgotten caches.",
        "combat": 1.0,
        "reward": 1.2,
        "puzzle": 1.65,
    },
    {
        "key": "hollow_march",
        "name": "The Hollow March",
        "emoji": "👑",
        "description": "A dead procession climbs toward Lastlight. Elite enemies are common and unusually vulnerable.",
        "combat": 1.1,
        "reward": 1.5,
        "puzzle": 0.9,
    },
    {
        "key": "quiet_deep",
        "name": "The Quiet Deep",
        "emoji": "🤫",
        "description": "For one day, the dungeon stops whispering. Explorers recover quickly, but treasure grows scarce.",
        "combat": 0.85,
        "reward": 0.9,
        "puzzle": 1.2,
    },
)

EXTENDED_ENEMIES: tuple[dict[str, Any], ...] = (
    {"name": "Lantern Thief", "emoji": "🕯️", "tier": 1, "hp": 40, "attack": 10, "defense": 2, "gold": 16, "xp": 17},
    {"name": "Gravebound Pilgrim", "emoji": "⛓️", "tier": 1, "hp": 51, "attack": 8, "defense": 5, "gold": 14, "xp": 18},
    {"name": "Spore Oracle", "emoji": "🔮", "tier": 2, "hp": 62, "attack": 15, "defense": 3, "gold": 25, "xp": 27},
    {"name": "Thorn Matriarch", "emoji": "🌹", "tier": 2, "hp": 88, "attack": 13, "defense": 7, "gold": 29, "xp": 31},
    {"name": "Memory Smith", "emoji": "🔨", "tier": 3, "hp": 108, "attack": 21, "defense": 9, "gold": 46, "xp": 48},
    {"name": "Cinder Seraph", "emoji": "🪽", "tier": 3, "hp": 98, "attack": 25, "defense": 6, "gold": 50, "xp": 52},
    {"name": "Nameless Duke", "emoji": "🎭", "tier": 4, "hp": 148, "attack": 29, "defense": 12, "gold": 72, "xp": 75},
    {"name": "Black Sun Priest", "emoji": "🌘", "tier": 4, "hp": 135, "attack": 33, "defense": 8, "gold": 78, "xp": 81},
    {"name": "Sentence Eater", "emoji": "📖", "tier": 5, "hp": 195, "attack": 37, "defense": 13, "gold": 96, "xp": 101},
    {"name": "Yesterday's Corpse", "emoji": "⌛", "tier": 5, "hp": 220, "attack": 35, "defense": 16, "gold": 105, "xp": 110},
)

EXTENDED_BOSSES: tuple[dict[str, Any], ...] = (
    {
        "name": "The Gaoler of Hours",
        "emoji": "⏰",
        "description": "Every strike ages your shadow while the thing inside the clock screams backward.",
        "hp": 680,
        "attack": 46,
        "defense": 23,
        "gold": 720,
        "xp": 760,
    },
    {
        "name": "Saint Caligo, Unremembered",
        "emoji": "🪽",
        "description": "A halo of erased names burns around the saint who was removed from every prayer.",
        "hp": 850,
        "attack": 53,
        "defense": 27,
        "gold": 900,
        "xp": 940,
    },
    {
        "name": "The Author Beneath",
        "emoji": "✒️",
        "description": "It lifts its pen. The room becomes a sentence, and you become the final word.",
        "hp": 1100,
        "attack": 61,
        "defense": 31,
        "gold": 1250,
        "xp": 1300,
    },
)
