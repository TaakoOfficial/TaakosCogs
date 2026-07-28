"""Character progression, subclass, talent, and title helpers."""

from __future__ import annotations

from typing import Any

from deepdelve.advanced_content import ABILITIES, BLESSINGS, SUBCLASSES, TALENT_TREES, TITLES


def available_abilities(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return abilities unlocked by the character's current level."""
    return [
        dict(ability)
        for ability in ABILITIES.get(profile.get("class_key", ""), ())
        if profile.get("level", 1) >= ability["level"]
    ]


def subclass_options(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return subclass choices for the profile's base class."""
    return SUBCLASSES.get(profile.get("class_key", ""), {})


def progression_bonuses(profile: dict[str, Any]) -> dict[str, int]:
    """Aggregate attributes, talents, subclass, prestige, blessings, and party bonuses."""
    attributes = profile.get("attributes", {})
    bonuses = {
        "hp": int(attributes.get("vitality", 0)) * 6,
        "mana": int(attributes.get("insight", 0)) * 4,
        "attack": int(attributes.get("might", 0)) * 2,
        "defense": int(attributes.get("vitality", 0)),
        "luck": int(attributes.get("fortune", 0)) * 2 + int(attributes.get("finesse", 0)),
    }
    subclass_key = profile.get("subclass", "")
    subclass = SUBCLASSES.get(profile.get("class_key", ""), {}).get(subclass_key, {})
    for stat, amount in subclass.get("bonuses", {}).items():
        bonuses[stat] = bonuses.get(stat, 0) + int(amount)
    talents = profile.get("talents", {})
    if profile.get("class_key") == "vanguard":
        bonuses["hp_percent"] = int(talents.get("unyielding", 0)) * 3
        bonuses["attack_percent"] = int(talents.get("weapon_mastery", 0)) * 2
    elif profile.get("class_key") == "arcanist":
        bonuses["mana_percent"] = int(talents.get("deep_reserves", 0)) * 5
        bonuses["ability_percent"] = int(talents.get("spellpower", 0)) * 3
    else:
        bonuses["critical"] = int(talents.get("precision", 0)) * 2
    prestige = min(10, max(0, int(profile.get("prestige", 0))))
    bonuses["hp_percent"] = bonuses.get("hp_percent", 0) + prestige * 2
    bonuses["attack_percent"] = bonuses.get("attack_percent", 0) + prestige
    for blessing_name in profile.get("blessings", []):
        blessing = next((entry for entry in BLESSINGS if entry["name"] == blessing_name), None)
        if blessing:
            bonuses[blessing["stat"]] = bonuses.get(blessing["stat"], 0) + blessing["amount"]
    # Scars are narrative records, not rewards for repeatedly losing encounters.
    party_bonus = profile.get("party_bonus", {})
    for stat, amount in party_bonus.items():
        bonuses[stat] = bonuses.get(stat, 0) + int(amount)
    party_role = profile.get("party_role", "")
    if party_role == "guardian":
        bonuses["defense"] += 3
    elif party_role == "striker":
        bonuses["attack"] += 3
    elif party_role == "support":
        bonuses["hp"] += 10
    elif party_role == "scout":
        bonuses["luck"] += 4
    guild_bonus = profile.get("guild_bonus", {})
    bonuses["luck"] += int(guild_bonus.get("luck", 0))
    return bonuses


def talent_definition(profile: dict[str, Any], talent_key: str) -> dict[str, Any] | None:
    """Resolve a talent belonging to the character's base class."""
    return next(
        (dict(talent) for talent in TALENT_TREES.get(profile.get("class_key", ""), ()) if talent["key"] == talent_key),
        None,
    )


def refresh_titles(profile: dict[str, Any]) -> list[str]:
    """Unlock earned titles and return newly earned display names."""
    unlocked = set(profile.get("titles", []))
    conditions = {
        "delver": profile.get("created", False),
        "giant_killer": profile.get("bosses", 0) >= 1,
        "loremaster": len(profile.get("lore", [])) >= 10,
        "oathkeeper": profile.get("contracts_completed", 0) >= 10,
        "riftwalker": profile.get("rifts_completed", 0) >= 1,
        "ascendant": profile.get("ascensions", 0) >= 1,
        "hardcore": profile.get("hardcore", False) and profile.get("deepest_floor", 0) >= 10,
        "champion": profile.get("arena_wins", 0) >= 10,
        "beacon": int(profile.get("morality", 0)) >= 70,
        "dreadbound": int(profile.get("morality", 0)) <= -70,
        "even_hand": (-29 <= int(profile.get("morality", 0)) <= 29 and len(profile.get("moral_deeds", [])) >= 12),
    }
    new_titles = []
    for key, earned in conditions.items():
        if earned and key not in unlocked:
            profile.setdefault("titles", []).append(key)
            new_titles.append(TITLES[key][0])
    if not profile.get("current_title") and profile.get("titles"):
        profile["current_title"] = profile["titles"][0]
    return new_titles
