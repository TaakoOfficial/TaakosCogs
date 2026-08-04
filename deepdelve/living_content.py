"""Authored and data-driven content for DeepDelve 5.0's living world."""

from __future__ import annotations

from typing import Any

FACTIONS: dict[str, dict[str, Any]] = {
    "lantern": {
        "name": "Lantern Covenant",
        "emoji": "☀️",
        "color": 0xF1C40F,
        "philosophy": "No life is expendable merely because the Deep has made saving it inconvenient.",
        "path": "radiant",
    },
    "concord": {
        "name": "Gray Concord",
        "emoji": "⚖️",
        "color": 0x7F8C8D,
        "philosophy": "Survival without truth is another kind of grave; every bargain must name its price.",
        "path": "pragmatic",
    },
    "court": {
        "name": "Veiled Court",
        "emoji": "🌑",
        "color": 0x512E5F,
        "philosophy": "Power is not wicked. Refusing to master it leaves it in crueler hands.",
        "path": "umbral",
    },
}

TENETS: dict[str, dict[str, Any]] = {
    "sheltering_flame": {
        "name": "Sheltering Flame",
        "path": "radiant",
        "kind": "defense",
        "description": "Defending below half health raises 8% additional guard.",
        "effect": {"guard_bonus": 0.08},
    },
    "mercy_repaid": {
        "name": "Mercy Repaid",
        "path": "radiant",
        "kind": "resource",
        "description": "The first potion each expedition restores 2 mana.",
        "effect": {"first_potion_mana": 2},
    },
    "honest_light": {
        "name": "Honest Light",
        "path": "radiant",
        "kind": "exploration",
        "description": "Honesty checks gain one effective rank.",
        "effect": {"check": "honesty", "check_bonus": 1},
    },
    "last_lantern": {
        "name": "Last Lantern",
        "path": "radiant",
        "kind": "offense",
        "description": "Deal 6% more damage while a boss is below 30% health.",
        "effect": {"execute_percent": 6},
    },
    "clean_hands": {
        "name": "Clean Hands",
        "path": "radiant",
        "kind": "utility",
        "description": "Inn rest costs 10% less.",
        "effect": {"rest_discount_percent": 10},
    },
    "oath_of_return": {
        "name": "Oath of Return",
        "path": "radiant",
        "kind": "survival",
        "description": "Once per battle, survive lethal damage at 1 health; rewards are reduced 10%.",
        "effect": {"death_save": 1, "death_save_reward_percent": -10},
    },
    "measured_breath": {
        "name": "Measured Breath",
        "path": "pragmatic",
        "kind": "resource",
        "description": "Defending restores 1 mana once every three combat turns.",
        "effect": {"defend_mana_cycle": 3},
    },
    "known_cost": {
        "name": "Known Cost",
        "path": "pragmatic",
        "kind": "economy",
        "description": "Faction services cost 10% less after their price is revealed.",
        "effect": {"service_discount_percent": 10},
    },
    "even_edge": {
        "name": "Even Edge",
        "path": "pragmatic",
        "kind": "offense",
        "description": "Basic attacks deal 5% more damage while no condition affects either combatant.",
        "effect": {"clean_attack_percent": 5},
    },
    "second_answer": {
        "name": "Second Answer",
        "path": "pragmatic",
        "kind": "utility",
        "description": "Once per dungeon, reroll a failed non-combat skill check.",
        "effect": {"check_reroll": 1},
    },
    "careful_pack": {
        "name": "Careful Pack",
        "path": "pragmatic",
        "kind": "exploration",
        "description": "The first consumable each battle has a 35% chance not to be consumed.",
        "effect": {"preserve_consumable_percent": 35},
    },
    "balanced_guard": {
        "name": "Balanced Guard",
        "path": "pragmatic",
        "kind": "defense",
        "description": "Gain 6% guard after changing from an ability to a basic action.",
        "effect": {"alternating_guard": 0.06},
    },
    "blood_price": {
        "name": "Blood Price",
        "path": "umbral",
        "kind": "resource",
        "description": "Once per battle, pay 6% maximum health to restore 3 mana.",
        "effect": {"blood_mana": 3, "blood_cost_percent": 6},
    },
    "predators_patience": {
        "name": "Predator's Patience",
        "path": "umbral",
        "kind": "offense",
        "description": "Deal 7% more damage after defending.",
        "effect": {"post_defend_damage_percent": 7},
    },
    "useful_fear": {
        "name": "Useful Fear",
        "path": "umbral",
        "kind": "exploration",
        "description": "Ruthlessness checks gain one effective rank.",
        "effect": {"check": "ruthlessness", "check_bonus": 1},
    },
    "borrowed_vigor": {
        "name": "Borrowed Vigor",
        "path": "umbral",
        "kind": "survival",
        "description": "Defeating an elite restores 6% maximum health but applies one-turn vulnerability.",
        "effect": {"elite_heal_percent": 6, "vulnerability": 1},
    },
    "shadow_cache": {
        "name": "Shadow Cache",
        "path": "umbral",
        "kind": "utility",
        "description": "Discover one additional hidden-route clue per named dungeon.",
        "effect": {"hidden_clue": 1},
    },
    "unyielding_claim": {
        "name": "Unyielding Claim",
        "path": "umbral",
        "kind": "defense",
        "description": "Taking a heavy hit grants 10% guard against the next attack.",
        "effect": {"heavy_revenge_guard": 0.10},
    },
}

FACTION_ARC_TITLES: dict[str, tuple[str, ...]] = {
    "lantern": (
        "Ash at the Gate",
        "Names of the Missing",
        "A Light Lent Freely",
        "The Unarmed Pilgrimage",
        "Mercy for a Monster",
        "The Cost of Sanctuary",
        "No One Left Below",
        "The Covenant Rekindled",
    ),
    "concord": (
        "Terms in Charcoal",
        "The Price Written First",
        "Witness to the Stair",
        "A Map with Two Truths",
        "The Necessary Lie",
        "Debts of Lastlight",
        "Judgment Without Comfort",
        "The Concord Restored",
    ),
    "court": (
        "A Shadow with Manners",
        "The Sealed Invitation",
        "Power Left Unclaimed",
        "The Knife at Council",
        "A Crown That Hungers",
        "The Cruel Mercy",
        "Master of the Whisper",
        "The Veil Made Whole",
    ),
}

FACTION_QUESTS: dict[str, tuple[dict[str, Any], ...]] = {
    faction: tuple(
        {
            "key": f"faction:{faction}:{index}",
            "name": title,
            "category": "faction",
            "faction": faction,
            "stage": index,
            "requirement": {"faction_reputation": max(0, (index - 1) * 5), "deepest_floor": index * 3},
            "objective": ("explore", "defeat", "choose", "recover")[index % 4],
            "target": 2 + index,
            "energy": 1,
            "reward": {"gold": 35 + index * 15, "xp": 25 + index * 20, "resolve": 1 if index in {4, 8} else 0},
            "outcomes": ("mercy", "honesty", "ambition", "ruthlessness"),
        }
        for index, title in enumerate(titles, start=1)
    )
    for faction, titles in FACTION_ARC_TITLES.items()
}

CHARACTER_NAMES = {
    "orra": "Orra Deepforge",
    "mara": "Captain Mara Venn",
    "vesper": "Vesper Quill",
    "rook": "Rook",
    "emberfox": "Emberfox",
    "mossback": "Mossback",
    "whisper": "Whisper",
    "brasswing": "Brasswing",
    "hollowhound": "Hollowhound",
}

CHARACTER_ARCS: dict[str, tuple[dict[str, Any], ...]] = {
    key: tuple(
        {
            "key": f"character:{key}:{stage}",
            "name": (
                f"{name}: First Confidence",
                f"{name}: The Unspoken Debt",
                f"{name}: What Remains",
            )[stage - 1],
            "category": "character",
            "character": key,
            "stage": stage,
            "requirement": {"relationship": (0, 8, 18)[stage - 1], "deepest_floor": (3, 12, 22)[stage - 1]},
            "objective": ("recover", "defeat", "choose")[stage - 1],
            "target": (2, 5, 1)[stage - 1],
            "energy": 1,
            "reward": {"gold": 40 * stage, "xp": 60 * stage, "relationship": 3},
            "outcomes": ("mercy", "honesty", "ambition", "ruthlessness"),
        }
        for stage in range(1, 4)
    )
    for key, name in CHARACTER_NAMES.items()
}

MAIN_ACT_NAMES = (
    "The Bell Without a Rope",
    "A Kingdom Under Lastlight",
    "The Cartographer's Sin",
    "War of the Remembered",
    "The Author Opens Its Eyes",
    "The Last Page Descends",
)

MAIN_CAMPAIGN_ACTS: tuple[dict[str, Any], ...] = tuple(
    {
        "key": f"living_act_{act}",
        "name": name,
        "floor": act * 5,
        "scenes": tuple(
            (
                f"Scene {scene}: {name} changes shape around the consequences carried from the floors above. "
                f"{'A witness asks what you are willing to save.' if scene % 2 else 'A sealed route demands a named price.'} "
                "The answer will be remembered by people who have not met you yet."
            )
            for scene in range(1, 7)
        ),
        "decisions": tuple(
            {
                "key": f"living_act_{act}:decision_{decision}",
                "prompt": (
                    "Choose who bears the consequence.",
                    "Choose which truth survives.",
                    "Choose what power may follow you home.",
                )[decision - 1],
                "options": ("mercy", "honesty", "ambition", "ruthlessness"),
            }
            for decision in range(1, 4)
        ),
        "reward": {"gold": 175 * act, "xp": 240 * act, "resolve": 2},
    }
    for act, name in enumerate(MAIN_ACT_NAMES, start=1)
)

REGION_KEYS = ("warrens", "fungal", "foundry", "court", "abyss")

DUNGEON_THEMES = (
    ("ossuary_of_rain", "Ossuary of Rain", "Rising water erases safe routes after every room.", "flood"),
    ("lanternless_hospice", "Lanternless Hospice", "Rescued shades may heal or betray their rescuer.", "trust"),
    ("mycelial_oracle", "Mycelial Oracle", "Spore prophecies reveal one danger while creating another.", "spores"),
    ("garden_of_second_names", "Garden of Second Names", "Speaking a true name changes the next encounter.", "names"),
    ("engine_of_saints", "Engine of Saints", "Heat and pressure must be routed between combat rooms.", "pressure"),
    ("memory_smeltery", "Memory Smeltery", "Sacrificed memories alter available skills until the boss falls.", "memory"),
    ("court_of_empty_chairs", "Court of Empty Chairs", "Every bargain seats a hostile witness at the final trial.", "witnesses"),
    ("masquerade_of_knives", "Masquerade of Knives", "Disguises open routes but make honest aid harder to secure.", "masks"),
    (
        "margin_beneath_reality",
        "Margin Beneath Reality",
        "Rooms can be rewritten once, preserving every crossed-out threat.",
        "revision",
    ),
    (
        "throne_of_the_last_reader",
        "Throne of the Last Reader",
        "The dungeon learns repeated tactics and counters them.",
        "adaptation",
    ),
)

NAMED_DUNGEONS: dict[str, dict[str, Any]] = {
    key: {
        "name": name,
        "region": REGION_KEYS[index // 2],
        "floor": 3 + index * 3,
        "mechanic": mechanic,
        "mechanic_key": mechanic_key,
        "rooms": 7,
        "checkpoints": (3, 5),
        "miniboss": f"{REGION_KEYS[index // 2]}:{('bell_keeper', 'saint_of_rust', 'unwelcome_heir')[index % 3]}",
        "boss": f"living_boss_{index + 1}",
        "energy_per_room": 1,
    }
    for index, (key, name, mechanic, mechanic_key) in enumerate(DUNGEON_THEMES)
}

EVENT_ARCHETYPES = (
    ("buried_witness", "A buried witness knows which expedition sealed the door.", "honesty", "Reveal a faction secret."),
    ("wounded_rival", "A wounded rival guards medicine meant for somebody else.", "mercy", "Choose who receives scarce aid."),
    (
        "hungry_altar",
        "An altar accepts health, treasure, or a sworn future favor.",
        "ambition",
        "Trade one resource for another.",
    ),
    (
        "deserters_map",
        "A deserter offers a safe map in exchange for silence.",
        "ruthlessness",
        "Protect or expose a dangerous guide.",
    ),
    ("echoing_child", "A child's echo insists the monster ahead is its parent.", "mercy", "Alter the next boss encounter."),
    (
        "false_epitaph",
        "Your own epitaph records a deed you have not committed.",
        "honesty",
        "Accept or reject a possible future.",
    ),
    (
        "chain_of_command",
        "Two Lastlight orders contradict each other word for word.",
        "ambition",
        "Choose whose authority survives.",
    ),
    (
        "sleeping_executioner",
        "A feared executioner sleeps beside the keys to a prison cart.",
        "ruthlessness",
        "Risk mercy, theft, or final judgment.",
    ),
    (
        "merchant_of_hours",
        "A merchant offers treasure in exchange for tomorrow's energy.",
        "ambition",
        "Refuse a prohibited energy bargain or expose it.",
    ),
    (
        "mirror_choir",
        "Three reflections confess mutually exclusive versions of your last deed.",
        "honesty",
        "Determine which memory becomes real.",
    ),
    (
        "sealed_refuge",
        "A refuge can be opened only by drawing danger toward it.",
        "mercy",
        "Protect strangers at an expedition cost.",
    ),
    (
        "crown_in_mud",
        "A powerless crown still commands the ghosts kneeling nearby.",
        "ruthlessness",
        "Destroy, wield, or study authority.",
    ),
)

DUNGEON_EVENTS: dict[str, dict[str, Any]] = {
    f"{region}:{event_key}": {
        "name": title.replace("_", " ").title(),
        "region": region,
        "text": text,
        "conviction": conviction,
        "purpose": purpose,
        "moral_choice": index < 6,
        "options": ("mercy", "honesty", "ambition", "ruthlessness"),
        "energy": 1,
        "reward_budget": 100,
    }
    for region_index, region in enumerate(REGION_KEYS)
    for index, (event_key, text, conviction, purpose) in enumerate(EVENT_ARCHETYPES)
    for title in (f"{event_key}_{region_index + 1}",)
}

PUZZLE_ARCHETYPES = (
    ("counterweight_tomb", "Balance names by the weight of the deeds attached to them.", ("insight", "honesty")),
    ("breathing_lock", "Match the lock's breath without inhaling its spores.", ("vitality", "profession")),
    ("pilgrims_cipher", "Reorder a prayer by the footsteps worn into the floor.", ("insight", "lore")),
)

LIVING_PUZZLES: dict[str, dict[str, Any]] = {
    f"{region}:{key}": {
        "name": f"{name} — {region.title()}",
        "region": region,
        "prompt": prompt,
        "solutions": solutions,
        "energy": 1,
        "reward_budget": 100,
    }
    for region, (key, prompt, solutions) in ((region, archetype) for region in REGION_KEYS for archetype in PUZZLE_ARCHETYPES)
    for name in (key.replace("_", " ").title(),)
}

ENEMY_ARCHETYPES = (
    ("votary", "Telegraphs a vow, then punishes breaking its stated rule.", "obey or deliberately dispel the vow"),
    ("mimic_scribe", "Copies the last ability used against it.", "alternate basic and skilled attacks"),
    ("grief_eater", "Grows stronger when the delver heals.", "heal before or after its feeding stance"),
    ("lantern_leech", "Drains mana before attempting a heavy attack.", "defend the drain or spend mana early"),
    ("chain_knight", "Binds one action type for two turns.", "maintain a varied action plan"),
    ("spore_diviner", "Predicts attacks but misreads defensive actions.", "feint with defense"),
    ("ash_collector", "Stores burn and poison damage before releasing it.", "avoid stacking conditions"),
    ("hollow_advocate", "Offers a bargain at half health.", "accept a cost or interrupt the bargain"),
    ("margin_hound", "Erases repeated actions from the combat menu temporarily.", "rotate tactics"),
)

LIVING_ENEMIES: dict[str, dict[str, Any]] = {
    f"{region}:{key}": {
        "name": f"{region.title()} {key.replace('_', ' ').title()}",
        "region": region,
        "tactic": tactic,
        "counter": counter,
        "family": key,
        "tier": region_index + 1,
        "codex_unlocks": (1, 3, 7),
    }
    for region_index, region in enumerate(REGION_KEYS)
    for key, tactic, counter in ENEMY_ARCHETYPES
}

MINIBOSS_ARCHETYPES = (
    ("bell_keeper", "Locks one combat action whenever the bell tolls."),
    ("saint_of_rust", "Corrodes the highest equipment stat until interrupted."),
    ("unwelcome_heir", "Changes moral invocation behavior for one turn."),
)

LIVING_MINIBOSSES: dict[str, dict[str, Any]] = {
    f"{region}:{key}": {
        "name": f"{key.replace('_', ' ').title()} of {region.title()}",
        "region": region,
        "mechanic": mechanic,
        "reward_budget": 175,
    }
    for region in REGION_KEYS
    for key, mechanic in MINIBOSS_ARCHETYPES
}

LIVING_BOSSES: dict[str, dict[str, Any]] = {
    f"living_boss_{index}": {
        "name": (
            "The Drowned Sexton",
            "Mother of Unlit Beds",
            "The Oracle in Bloom",
            "Gardener of Stolen Names",
            "Saint Caldera",
            "The Mnemonic Furnace",
            "The Unseated Judge",
            "Duchess Lastmask",
            "The Redactor Below",
            "The Last Reader",
        )[index - 1],
        "dungeon": tuple(NAMED_DUNGEONS)[index - 1],
        "phases": 3,
        "mechanic": tuple(NAMED_DUNGEONS.values())[index - 1]["mechanic"],
        "moral_decision": True,
        "reward_budget": 300,
    }
    for index in range(1, 11)
}

SET_THEMES = (
    ("dawnwarden", "Dawnwarden", "radiant", "guard after healing"),
    ("hospitaller", "Last Hospitaller", "radiant", "convert excess healing into ward"),
    ("truthbearer", "Truthbearer", "radiant", "reveal and punish deceptive intents"),
    ("pilgrim", "Unarmed Pilgrim", "radiant", "gain power from unused consumables"),
    ("arbiter", "Gray Arbiter", "pragmatic", "alternate actions for tempo"),
    ("cartographer", "Final Cartographer", "pragmatic", "exploit discovered enemy counters"),
    ("debtscribe", "Debt-Scribe", "pragmatic", "bank mana for a later turn"),
    ("witness", "Last Witness", "pragmatic", "reroll one failed check per dungeon"),
    ("veilknife", "Veilknife", "umbral", "trade health for finishing damage"),
    ("crownless", "Crownless Heir", "umbral", "gain guard after taking a heavy hit"),
    ("sin_eater", "Sin-Eater", "umbral", "consume conditions for recovery"),
    ("red_hand", "Red Right Hand", "umbral", "improve the next action after intimidation"),
)

LIVING_ITEM_SETS: dict[str, dict[str, Any]] = {
    key: {
        "name": name,
        "path": path,
        "classes": ("vanguard", "shadow", "arcanist"),
        "two": f"Adopt a balanced {identity} stance.",
        "three": f"Complete the set to {identity}.",
        "two_stats": ({"defense": 6} if path == "radiant" else {"luck": 4} if path == "pragmatic" else {"attack": 4}),
        "three_stats": ({"hp": 12} if path == "radiant" else {"mana": 9} if path == "pragmatic" else {"defense": 4}),
        "pieces": tuple(
            {
                "slot": slot,
                "name": f"{name} {suffix}",
                "bound": True,
                "power_budget": 100,
            }
            for slot, suffix in (("weapon", "Instrument"), ("armor", "Vestment"), ("charm", "Token"))
        ),
        "identity": identity,
    }
    for key, name, path, identity in SET_THEMES
}

RELIC_THEMES = (
    ("bell_clapper", "Clapper of the Fifth Bell", "Delay one heavy intent each boss fight."),
    ("orra_first_hammer", "Orra's First Hammer", "Crafting commissions return one bonus material."),
    ("mara_broken_badge", "Mara's Broken Badge", "Reveal whether a contract target has an elite variant."),
    ("vesper_red_ink", "Vesper's Red Ink", "Lore checks gain one effective rank."),
    ("rooks_loaded_die", "Rook's Loaded Die", "Once per dungeon, turn the lowest skill-check roll into an average roll."),
    ("foxfire_vial", "Foxfire Vial", "The first burn applied each battle lasts one additional turn."),
)

LIVING_RELICS: dict[str, dict[str, Any]] = {
    f"{key}_{tier}": {
        "name": f"{name}{' II' if tier == 2 else ' III' if tier == 3 else ''}",
        "description": description,
        "tier": tier,
        "bound": True,
        "power_budget": 75 + tier * 25,
        "duplicate_currency": 12 * tier,
        "slot": ("weapon", "armor", "charm")[(tier - 1) % 3],
        "effect": ("silence", "mending", "fortune", "warding", "clarity")[(tier - 1) % 5],
    }
    for tier in range(1, 6)
    for key, name, description in RELIC_THEMES
}

CONSUMABLE_ARCHETYPES = (
    ("ward_chalk", "Ward Chalk", "Gain guard before the next enemy intent."),
    ("truth_salt", "Truth Salt", "Reveal the next two enemy intents."),
    ("grave_mint", "Grave Mint", "Cleanse one condition and lose 2 mana."),
    ("borrowed_spark", "Borrowed Spark", "Restore mana now and take damage after three turns."),
    ("smoke_thread", "Smoke Thread", "Reroll a non-boss encounter."),
    ("memory_nail", "Memory Nail", "Prevent an enemy from changing intent once."),
)

LIVING_CONSUMABLES: dict[str, dict[str, Any]] = {
    f"{key}_{grade}": {
        "name": f"{name} {('I', 'II', 'III', 'IV')[grade - 1]}",
        "description": description,
        "grade": grade,
        "value": 15 * grade,
        "bound": False,
        "emoji": ("🛡️", "🧂", "🌿", "⚡", "💨", "🔩")[tuple(entry[0] for entry in CONSUMABLE_ARCHETYPES).index(key)],
        "region": min(4, grade),
        "effect": ("guard", "reroll", "cleanse", "mana", "escape", "reroll")[
            tuple(entry[0] for entry in CONSUMABLE_ARCHETYPES).index(key)
        ],
        "power": ((20 + grade * 8) if key == "ward_chalk" else (5 + grade * 3) if key == "borrowed_spark" else grade),
    }
    for grade in range(1, 5)
    for key, name, description in CONSUMABLE_ARCHETYPES
}

LIVING_RECIPES: dict[str, dict[str, Any]] = {
    f"recipe:{region}:{index}": {
        "name": f"{region.title()} Commission {index}",
        "region": region,
        "profession": ("smith", "alchemist", "scribe", "scout")[index % 4],
        "mastery": index * 3,
        "gold_cost": 35 + index * 20,
        "materials": {("iron", "silk", "ember", "essence", "voidglass")[index % 5]: 1 + index // 2},
        "output": ("equipment", "consumable", "relic_fragment")[index % 3],
        "bound": index % 3 == 2,
    }
    for region in REGION_KEYS
    for index in range(1, 7)
}

CONTRACT_OBJECTIVES = (
    ("hunt", "Defeat enemies from the marked family."),
    ("study", "Reveal bestiary research milestones."),
    ("recover", "Recover expedition objects."),
    ("survive", "Clear encounters while carrying a dangerous condition."),
    ("resolve", "Complete dungeon events through a specified conviction."),
    ("delve", "Clear rooms in a named dungeon."),
)

CONTRACT_TEMPLATES: dict[str, dict[str, Any]] = {
    f"contract:{objective}:{tier}": {
        "name": f"{objective.title()} Contract {tier}",
        "objective": objective,
        "description": description,
        "tier": tier,
        "target": 2 + tier * 2,
        "energy_budget": min(12, 3 + tier),
        "reward": {"gold": 40 + tier * 30, "xp": 35 + tier * 25},
    }
    for objective, description in CONTRACT_OBJECTIVES
    for tier in range(1, 7)
}

SEASON_CHAPTERS: tuple[dict[str, Any], ...] = tuple(
    {
        "key": f"season_chapter_{index}",
        "name": (
            "The Thawing Bell",
            "Procession of Empty Armor",
            "The Mushroom Parliament",
            "Ashfall Election",
            "The Court Remembers Summer",
            "A Moon Below Ground",
            "The Saints Go Missing",
            "Lastlight's Longest Night",
            "The Cartographers Return",
            "Trial of the Three Lanterns",
            "The Deep Writes Back",
            "A Door Marked Tomorrow",
        )[index - 1],
        "index": index,
        "scenes": 3,
        "energy_budget": 8,
        "reward": {"gold": 120 + index * 15, "xp": 150 + index * 20, "cosmetic": f"archive_mark_{index}"},
        "permanent": True,
    }
    for index in range(1, 13)
)

LIVING_TITLES: dict[str, tuple[str, str]] = {
    "covenant_voice": ("Voice of the Covenant", "Complete the Lantern Covenant arc."),
    "gray_arbiter": ("Gray Arbiter", "Complete the Gray Concord arc."),
    "veilmaster": ("Master of the Veil", "Complete the Veiled Court arc."),
    "redeemed": ("The Road Home", "Complete a redemption journey without erasing the past."),
    "twice_fallen": ("Twice-Fallen", "Complete a corruption journey after once becoming Radiant."),
    "nemesis_bane": ("Bane of Names", "Defeat five personal Nemeses."),
    "sanctum_keeper": ("Keeper of Echoes", "Fully restore the personal Sanctum."),
    "atlas_complete": ("Walker of Every Road", "Discover every named dungeon."),
}
