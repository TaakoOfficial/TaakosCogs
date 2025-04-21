"""Utility functions for creating visual elements in Fable."""
import discord
from datetime import datetime
from typing import List, Dict, Optional

def create_timeline_embed(
    events: List[Dict],
    char_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    event_type: Optional[str] = None
) -> discord.Embed:
    """Create a visual timeline embed for character events."""
    embed = discord.Embed(
        title=f"📅 Timeline: {char_name}",
        color=0x7289DA
    )

    if not events:
        embed.description = "No events found for this timeline."
        return embed

    # Filter events by date range if provided
    if start_date or end_date:
        filtered_events = []
        start = datetime.fromisoformat(start_date) if start_date else datetime.min
        end = datetime.fromisoformat(end_date) if end_date else datetime.max
        
        for event in events:
            event_date = datetime.fromisoformat(event["date"])
            if start <= event_date <= end:
                filtered_events.append(event)
        events = filtered_events

    # Filter by event type if provided
    if event_type:
        events = [e for e in events if e.get("type", "").lower() == event_type.lower()]

    # Sort events by date
    events.sort(key=lambda x: x["date"])

    # Create timeline visualization
    timeline = ""
    for i, event in enumerate(events):
        date = datetime.fromisoformat(event["date"]).strftime("%Y-%m-%d")
        event_type = event.get("type", "Event")
        
        # Add visual elements based on event type
        icons = {
            "milestone": "🎯",
            "relationship": "👥",
            "story": "📖",
            "location": "📍",
            "development": "📈"
        }
        icon = icons.get(event_type.lower(), "•")
        
        timeline += f"{icon} **{date}** - {event['title']}\n"
        if event.get("description"):
            timeline += f"┗━ {event['description']}\n"
        if i < len(events) - 1:
            timeline += "┃\n"  # Vertical line connecting events

    if timeline:
        # Split timeline if it's too long
        if len(timeline) > 4000:
            parts = []
            current_part = ""
            for line in timeline.split("\n"):
                if len(current_part) + len(line) + 1 > 1000:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += f"\n{line}" if current_part else line
            if current_part:
                parts.append(current_part)

            for i, part in enumerate(parts, 1):
                embed.add_field(
                    name=f"Timeline Part {i}/{len(parts)}", 
                    value=part, 
                    inline=False
                )
        else:
            embed.description = timeline

    event_counts = {}
    for event in events:
        event_type = event.get("type", "Event")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    if event_counts:
        stats = "\n".join(f"{icons.get(t.lower(), '•')} {t}: {count}" for t, count in event_counts.items())
        embed.add_field(name="Event Statistics", value=stats, inline=False)

    return embed

def create_relationship_graph(relationships: Dict) -> str:
    """
    Create a DOT format graph of character relationships.
    Returns the DOT string that can be rendered into an image.
    """
    dot = [
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=box, style=rounded];",
        "  edge [len=2];"
    ]

    # Add nodes and edges
    for char, rels in relationships.items():
        dot.append(f'  "{char}" [label="{char}"];')
        for rel_type, targets in rels.items():
            for target in targets:
                color = {
                    "ally": "green",
                    "rival": "red",
                    "neutral": "gray",
                    "family": "blue"
                }.get(rel_type, "black")
                dot.append(f'  "{char}" -> "{target}" [color={color}, label="{rel_type}"];')

    dot.append("}")
    return "\n".join(dot)

def create_location_map(locations: Dict) -> str:
    """
    Create a DOT format graph of connected locations.
    Returns the DOT string that can be rendered into an image.
    """
    dot = [
        "graph G {",
        "  node [shape=box, style=filled];",
        "  edge [len=3];"
    ]

    # Add nodes with custom shapes based on category
    for loc_name, loc_data in locations.items():
        category = loc_data.get("category", "").lower()
        color = {
            "tavern": "brown",
            "castle": "gray",
            "house": "green",
            "shop": "yellow",
            "dungeon": "darkred"
        }.get(category, "lightblue")
        
        dot.append(f'  "{loc_name}" [fillcolor={color}];')

    # Add connections
    for loc_name, loc_data in locations.items():
        for conn in loc_data.get("connected_to", []):
            target = conn["location"]
            if loc_name < target:  # Avoid duplicate edges
                dot.append(f'  "{loc_name}" -- "{target}";')

    dot.append("}")
    return "\n".join(dot)
