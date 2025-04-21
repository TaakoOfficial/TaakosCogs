"""Templates for Google Docs exports."""
from datetime import datetime

def format_timeline(events: list) -> str:
    """Format character timeline for export."""
    timeline = "『 CHARACTER TIMELINE 』\n\n"
    
    if not events:
        return timeline + "No events recorded."
        
    events.sort(key=lambda x: x["date"])
    
    for event in events:
        date = datetime.fromisoformat(event["date"]).strftime("%Y-%m-%d")
        event_type = event.get("type", "Event")
        icons = {
            "milestone": "🎯",
            "relationship": "👥",
            "story": "📖",
            "location": "📍",
            "development": "📈"
        }
        icon = icons.get(event_type.lower(), "•")
        
        timeline += f"{icon} {date} - {event['title']}\n"
        if event.get("description"):
            timeline += f"    {event['description']}\n"
        timeline += "\n"
    
    return timeline

def format_relationships(relationships: dict) -> str:
    """Format character relationships for export."""
    content = "『 CHARACTER RELATIONSHIPS 』\n\n"
    
    if not relationships:
        return content + "No relationships recorded."
        
    for rel_type, rel_list in relationships.items():
        if rel_list:
            content += f"━━━ {rel_type.upper()} ━━━\n"
            for rel in rel_list:
                content += f"• {rel}\n"
            content += "\n"
    
    return content

def get_character_template(character: dict) -> str:
    """Generate a formatted Google Doc template for a character profile."""
    template = f"""
━━━━━━━━━━━━━━━ 𝐈𝐃𝐄𝐍𝐓𝐈𝐓𝐘 ━━━━━━━━━━━━━━━
⌾ Full Name: {character.get('full_name', character.get('name', 'Unknown'))}
⌾ Species: {character.get('species', 'N/A')}
⌾ Gender: {character.get('gender', 'N/A')}
⌾ Date of Birth: {character.get('date_of_birth', 'N/A')}
⌾ Age: {character.get('age', 'N/A')}
⌾ Age Appearance: {character.get('age_appearance', 'N/A')}
⌾ True Age: {character.get('true_age', 'N/A')}

━━━━━━━━━━━━━━━ 𝐁𝐀𝐒𝐈𝐂𝐒 ━━━━━━━━━━━━━━━
⌾ Ethnicity: {character.get('ethnicity', 'N/A')}
⌾ Occupation: {character.get('occupation', 'N/A')}
⌾ Height: {character.get('height', 'N/A')}
⌾ Weight: {character.get('weight', 'N/A')}
⌾ Sexual Orientation: {character.get('sexual_orientation', 'N/A')}
⌾ Zodiac: {character.get('zodiac', 'N/A')}
⌾ Alignment: {character.get('alignment', 'N/A')}

━━━━━━━━━━━━━━━ 𝐏𝐄𝐑𝐒𝐎𝐍𝐀𝐋𝐈𝐓𝐘 ━━━━━━━━━━━━━━━
⌾ Traits:
{chr(10).join(f"  • {trait}" for trait in character.get('traits', []) or ['N/A'])}

⌾ Goals:
{chr(10).join(f"  • {goal}" for goal in character.get('goals', []) or ['N/A'])}

⌾ Languages:
{chr(10).join(f"  • {lang}" for lang in character.get('languages', []) or ['N/A'])}

⌾ Notable Items:
{chr(10).join(f"  • {item}" for item in character.get('inventory', []) or ['N/A'])}

━━━━━━━━━━━━━━━ 𝐑𝐄𝐋𝐀𝐓𝐈𝐎𝐍𝐒𝐇𝐈𝐏𝐒 ━━━━━━━━━━━━━━━
"""
    
    # Add relationships
    for rel_type, rel_list in character.get('relationships', {}).items():
        if rel_list:
            template += f"\n⌾ {rel_type.capitalize()}s:\n"
            template += "\n".join(f"  • {rel}" for rel in rel_list)
            template += "\n"

    # Add description and background
    template += "\n━━━━━━━━━━━━━━━ 𝐃𝐄𝐒𝐂𝐑𝐈𝐏𝐓𝐈𝐎𝐍 ━━━━━━━━━━━━━━━\n"
    template += character.get('description', 'No description available.')
    
    if character.get('background'):
        template += "\n\n━━━━━━━━━━━━━━━ 𝐁𝐀𝐂𝐊𝐆𝐑𝐎𝐔𝐍𝐃 ━━━━━━━━━━━━━━━\n"
        template += character['background']
    
    # Add development timeline if available
    if character.get('milestones') or character.get('story_arcs'):
        template += "\n\n━━━━━━━━━━━━━━━ 𝐃𝐄𝐕𝐄𝐋𝐎𝐏𝐌𝐄𝐍𝐓 ━━━━━━━━━━━━━━━\n"
        
        if character.get('milestones'):
            template += "\n🎯 Milestones:\n"
            for milestone in sorted(character['milestones'], key=lambda x: x['date']):
                date = datetime.fromisoformat(milestone['date']).strftime("%Y-%m-%d")
                template += f"• {date} - {milestone['title']}\n"
                template += f"  {milestone['description']}\n"
        
        if character.get('story_arcs'):
            template += "\n📖 Story Arcs:\n"
            for arc in character['story_arcs']:
                template += f"• {arc['title']} ({arc['status']})\n"
                template += f"  {arc['description']}\n"
    
    return template

def get_location_template(location: dict) -> str:
    """Generate a formatted template for location details."""
    template = f"""
━━━━━━━━━━━━━━━ 𝐋𝐎𝐂𝐀𝐓𝐈𝐎𝐍 𝐃𝐄𝐓𝐀𝐈𝐋𝐒 ━━━━━━━━━━━━━━━
⌾ Name: {location['name']}
⌾ Category: {location.get('category', 'N/A')}

📝 Description:
{location['description']}

"""
    
    if location.get('connected_to'):
        template += "\n━━━ Connected Locations ━━━\n"
        for conn in location['connected_to']:
            template += f"• {conn['location']}"
            if conn.get('description'):
                template += f" - {conn['description']}"
            template += "\n"
    
    if location.get('visits'):
        template += "\n━━━ Recent Visits ━━━\n"
        for visit in sorted(location['visits'], key=lambda x: x['timestamp'], reverse=True)[:5]:
            date = datetime.fromisoformat(visit['timestamp']).strftime("%Y-%m-%d")
            template += f"• {date} - {visit['character']}"
            if visit.get('note'):
                template += f" ({visit['note']})"
            template += "\n"
    
    return template
