"""Document templates with consistent styling for Fable."""
import discord
from typing import Dict, Any, List
from .style_utils import FableEmbed

class DocumentTemplates:
    """Handles consistent document formatting for exports and records."""

    @staticmethod
    async def character_profile_doc(
        name: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate a formatted character profile document.
        
        Parameters
        ----------
        name : str
            Character name
        data : Dict[str, Any]
            Character data
            
        Returns
        -------
        List[Dict[str, Any]]
            List of sections for the document
        """
        sections = [
            {
                "title": "Character Profile",
                "content": f"# {name}\n\n{data.get('description', 'No description available.')}\n"
            }
        ]
        
        # Identity Section
        identity = []
        if data.get("full_name"):
            identity.append(f"**Full Name:** {data['full_name']}")
        if data.get("species"):
            identity.append(f"**Species:** {data['species']}")
        if data.get("gender"):
            identity.append(f"**Gender:** {data['gender']}")
        if identity:
            sections.append({
                "title": "Identity",
                "content": "\n".join(identity)
            })
            
        # Background
        if data.get("background"):
            sections.append({
                "title": "Background",
                "content": data["background"]
            })
            
        # Traits and Skills
        traits_content = []
        if data.get("traits"):
            traits_content.append("## Traits\n" + "\n".join(f"- {t}" for t in data["traits"]))
        if data.get("languages"):
            traits_content.append("## Languages\n" + "\n".join(f"- {l}" for l in data["languages"]))
        if traits_content:
            sections.append({
                "title": "Traits & Skills",
                "content": "\n\n".join(traits_content)
            })
            
        return sections

    @staticmethod
    async def location_doc(
        name: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate a formatted location document.
        
        Parameters
        ----------
        name : str
            Location name
        data : Dict[str, Any]
            Location data
            
        Returns
        -------
        List[Dict[str, Any]]
            List of sections for the document
        """
        sections = [
            {
                "title": "Location Profile",
                "content": f"# {name}\n\n{data.get('description', 'No description available.')}\n"
            }
        ]
        
        # Features
        if data.get("features"):
            sections.append({
                "title": "Notable Features",
                "content": "\n".join(f"- {f}" for f in data["features"])
            })
            
        # Connections
        if data.get("connected_to"):
            connections = []
            for conn in data["connected_to"]:
                conn_text = f"- {conn['location']}"
                if conn.get("description"):
                    conn_text += f"\n  *{conn['description']}*"
                connections.append(conn_text)
            sections.append({
                "title": "Connected Locations",
                "content": "\n".join(connections)
            })
            
        # History
        if data.get("events"):
            events = []
            for event in sorted(data["events"], key=lambda e: e["timestamp"]):
                events.append(f"- [{event['timestamp']}] {event['title']}")
                if event.get("description"):
                    events.append(f"  *{event['description']}*")
            sections.append({
                "title": "Location History",
                "content": "\n".join(events)
            })
            
        return sections

    @staticmethod
    async def timeline_doc(
        events: List[Dict[str, Any]],
        title: str
    ) -> List[Dict[str, Any]]:
        """
        Generate a formatted timeline document.
        
        Parameters
        ----------
        events : List[Dict[str, Any]]
            List of events
        title : str
            Timeline title
            
        Returns
        -------
        List[Dict[str, Any]]
            List of sections for the document
        """
        sections = [
            {
                "title": title,
                "content": "# Timeline Overview\n"
            }
        ]
        
        # Group events by type
        event_types = {}
        for event in sorted(events, key=lambda e: e["date"]):
            event_type = event.get("type", "Other")
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append(event)
            
        # Create sections for each event type
        for event_type, type_events in event_types.items():
            content = []
            for event in type_events:
                content.append(f"## {event['date']} - {event['title']}")
                if event.get("description"):
                    content.append(f"{event['description']}\n")
            sections.append({
                "title": f"{event_type} Events",
                "content": "\n".join(content)
            })
            
        return sections

    @staticmethod
    async def relationship_doc(
        relationships: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate a formatted relationship document.
        
        Parameters
        ----------
        relationships : Dict[str, Any]
            Relationship data
            
        Returns
        -------
        List[Dict[str, Any]]
            List of sections for the document
        """
        sections = [
            {
                "title": "Relationship Network",
                "content": "# Character Relationships\n"
            }
        ]
        
        # Group by relationship type
        rel_types = {
            "ally": "Allies",
            "rival": "Rivals",
            "family": "Family",
            "neutral": "Neutral",
            "custom": "Other Relationships"
        }
        
        grouped = {k: [] for k in rel_types.values()}
        
        for rel_id, rel_data in relationships.items():
            rel_type = rel_data.get("type", "custom").lower()
            group = rel_types.get(rel_type, "Other Relationships")
            intensity = "⭐" * rel_data.get("intensity", 1)
            
            rel_text = f"- {rel_data['target']} {intensity}"
            if rel_data.get("description"):
                rel_text += f"\n  *{rel_data['description']}*"
            
            grouped[group].append(rel_text)
            
        # Create sections for each relationship type
        for group_name, relationships in grouped.items():
            if relationships:
                sections.append({
                    "title": group_name,
                    "content": "\n".join(relationships)
                })
                
        return sections
