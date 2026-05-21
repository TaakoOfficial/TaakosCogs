"""Character templates for different genres."""

FANTASY_TEMPLATE = {
    "description": "A brave adventurer in a magical world...",
    "fields": {
        "species": "Human/Elf/Dwarf/etc.",
        "alignment": "Lawful Good/Neutral/etc.",
        "traits": ["Brave", "Curious", "Determined"],
        "languages": ["Common", "Elvish"],
        "inventory": ["Sword", "Spellbook", "Adventuring Pack"],
        "goals": ["Master the arcane arts", "Explore the realm"]
    }
}

MODERN_TEMPLATE = {
    "description": "A contemporary character living in the modern world...",
    "fields": {
        "occupation": "Student/Professional/Artist/etc.",
        "traits": ["Ambitious", "Creative", "Resourceful"],
        "languages": ["English", "Spanish"],
        "inventory": ["Smartphone", "Laptop", "Car Keys"],
        "goals": ["Advance career", "Travel the world"]
    }
}

SCIFI_TEMPLATE = {
    "description": "A character in a futuristic setting...",
    "fields": {
        "species": "Human/Android/Alien/etc.",
        "occupation": "Starship Captain/Engineer/Scientist/etc.",
        "traits": ["Technical", "Adaptable", "Innovative"],
        "languages": ["Galactic Standard", "Binary"],
        "inventory": ["Neural Implant", "Plasma Pistol", "Holo-device"],
        "goals": ["Explore new worlds", "Advance technology"]
    }
}

SUPERNATURAL_TEMPLATE = {
    "description": "A character with supernatural abilities or origins...",
    "fields": {
        "species": "Vampire/Werewolf/Ghost/etc.",
        "true_age": "Actual age (if immortal/supernatural)",
        "age_appearance": "How old they appear",
        "traits": ["Mysterious", "Powerful", "Tormented"],
        "inventory": ["Magical Artifacts", "Ancient Relics"],
        "goals": ["Control powers", "Find redemption"]
    }
}

def get_template(genre: str) -> dict:
    """Get a character template for a specific genre."""
    templates = {
        "fantasy": FANTASY_TEMPLATE,
        "modern": MODERN_TEMPLATE,
        "scifi": SCIFI_TEMPLATE,
        "supernatural": SUPERNATURAL_TEMPLATE
    }
    return templates.get(genre.lower(), FANTASY_TEMPLATE)
