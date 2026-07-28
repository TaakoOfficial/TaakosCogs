"""NPC and companion relationships, favors, gifts, conflicts, and mail."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deepdelve.living_content import CHARACTER_NAMES
from deepdelve.systems.dungeon_depth import create_rumor
from deepdelve.systems.morality import morality_path

GIFT_PREFERENCES = {
    "orra": "iron",
    "mara": "silk",
    "vesper": "essence",
    "rook": "voidglass",
    "emberfox": "ember",
    "mossback": "silk",
    "whisper": "essence",
    "brasswing": "iron",
    "hollowhound": "voidglass",
}


def ensure_relationships(profile: dict[str, Any]) -> dict[str, Any]:
    """Normalize all character relationships and mailbox state."""
    relationships = profile.setdefault("relationships", {})
    old_reputation = profile.get("npc_reputation", {})
    for key in CHARACTER_NAMES:
        entry = relationships.setdefault(
            key, {"trust": int(old_reputation.get(key, 0)), "conflict": 0, "flags": [], "gift_date": ""},
        )
        entry.setdefault("trust", int(old_reputation.get(key, 0)))
        entry.setdefault("conflict", 0)
        entry.setdefault("flags", [])
        entry.setdefault("gift_date", "")
        entry.setdefault("favor_week", "")
    profile.setdefault("mailbox", [])
    profile.setdefault("mail_read", [])
    return relationships


def relationship_level(entry: dict[str, Any]) -> str:
    """Translate trust and conflict into a visible relationship."""
    trust = int(entry.get("trust", 0))
    conflict = int(entry.get("conflict", 0))
    if conflict >= 15:
        return "Hostile"
    if conflict >= 8:
        return "Strained"
    if trust >= 30:
        return "Bonded"
    if trust >= 20:
        return "Confidant"
    if trust >= 10:
        return "Trusted"
    if trust >= 4:
        return "Acquaintance"
    return "Stranger"


def change_relationship(profile: dict[str, Any], key: str, *, trust: int = 0, conflict: int = 0, flag: str = "") -> int:
    """Change and bound a relationship, optionally remembering why."""
    relationships = ensure_relationships(profile)
    if key not in relationships:
        return 0
    entry = relationships[key]
    old = int(entry["trust"])
    entry["trust"] = max(0, min(50, old + int(trust)))
    entry["conflict"] = max(0, min(50, int(entry["conflict"]) + int(conflict)))
    if flag and flag not in entry["flags"]:
        entry["flags"].append(flag)
    return int(entry["trust"]) - old


def generate_mail(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Add idempotent letters caused by milestones and remembered choices."""
    ensure_relationships(profile)
    mailbox = profile["mailbox"]
    existing = {letter["key"] for letter in mailbox}
    candidates = []
    path = morality_path(profile)["key"]
    if path in {"beacon", "dreadbound"}:
        candidates.append(
            {
                "key": f"path:{path}",
                "from": "The Lastlight Gazette",
                "subject": "The town has noticed",
                "body": f"Citizens have begun calling you {path.title()}. Some speak with hope; others lower their voices.",
            },
        )
    for key, entry in profile["relationships"].items():
        level = relationship_level(entry)
        if level in {"Confidant", "Bonded", "Hostile"}:
            candidates.append(
                {
                    "key": f"relationship:{key}:{level.lower()}",
                    "from": CHARACTER_NAMES[key],
                    "subject": f"Where we stand: {level}",
                    "body": (
                        "What happened below has changed the terms between us. Come speak when you are ready; "
                        "silence will not make the memory smaller."
                    ),
                },
            )
    for letter in candidates:
        if letter["key"] not in existing:
            mailbox.append(letter)
            existing.add(letter["key"])
    return mailbox


def world_echoes(profile: dict[str, Any]) -> list[str]:
    """Summarize concrete persistent consequences."""
    lines = []
    for flag in profile.get("quests_v2", {}).get("choice_flags", [])[-8:]:
        body = flag.removeprefix("quest_outcome:")
        key, outcome = body.rsplit(":", maxsplit=1)
        lines.append(f"📜 **{key.replace('_', ' ').title()}** was resolved through **{outcome.title()}**.")
    for flag in profile.get("legacy", {}).get("consequence_flags", [])[-5:]:
        lines.append(f"⚖️ {flag.replace(':', ' — ').replace('_', ' ').title()}.")
    for key, entry in ensure_relationships(profile).items():
        level = relationship_level(entry)
        if level in {"Bonded", "Hostile"}:
            lines.append(f"👤 **{CHARACTER_NAMES[key]}** now considers you **{level}**.")
    return lines or ["The world has not yet learned enough about you to echo."]


def give_gift(profile: dict[str, Any], key: str, material: str) -> tuple[bool, str]:
    """Give one daily material gift with authored preferences."""
    relationships = ensure_relationships(profile)
    if key not in relationships:
        return False, "Unknown Lastlight relationship."
    if material not in profile.get("materials", {}):
        return False, "Choose iron, silk, ember, essence, or voidglass."
    if int(profile["materials"].get(material, 0)) < 1:
        return False, f"You have no {material} to give."
    today = datetime.now(timezone.utc).date().isoformat()
    entry = relationships[key]
    if entry["gift_date"] == today:
        return False, "You have already offered this character a gift today."
    profile["materials"][material] -= 1
    entry["gift_date"] = today
    gain = 2 if GIFT_PREFERENCES[key] == material else 1
    change_relationship(profile, key, trust=gain, flag=f"gift:{material}")
    preference = " It was exactly the right choice." if gain == 2 else ""
    return True, f"🎁 {CHARACTER_NAMES[key]} accepts the {material}. **+{gain} trust.**{preference}"


def request_favor(profile: dict[str, Any], key: str) -> tuple[bool, str]:
    """Request one weekly non-power favor from a trusted character."""
    relationships = ensure_relationships(profile)
    if key not in relationships:
        return False, "Unknown Lastlight relationship."
    entry = relationships[key]
    if int(entry["trust"]) < 10:
        return False, "Favors require at least 10 trust."
    if int(entry["conflict"]) >= 15:
        return False, "This relationship is too hostile for a favor."
    today = datetime.now(timezone.utc).date()
    week = f"{today.isocalendar().year}-w{today.isocalendar().week:02d}"
    if entry["favor_week"] == week:
        return False, "You have already requested this character's favor this week."
    if profile.get("active_rumor"):
        return False, "Resolve the active personal hunt before requesting another lead."
    entry["favor_week"] = week
    rumor = create_rumor(profile)
    return True, f"🗺️ {CHARACTER_NAMES[key]} shares a private lead: **{rumor['name']}** — {rumor['description']}"
