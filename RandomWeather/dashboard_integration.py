from AAA3A_utils import CogManager  # Edited by Taako

def register_dashboard_settings(cog):
    """Register settings for the AAA3A Dashboard Cog."""
    # Edited by Taako
    CogManager.register_cog_settings(
        cog=cog,
        settings={
            "role_id": {
                "type": "role",
                "description": "Role to tag for weather updates.",
                "conditional_disable": {"field": "tag_role", "value": False},  # Grayed out if tag_role is False
            },
            "channel_id": {"type": "channel", "description": "Channel for weather updates."},
            "tag_role": {"type": "bool", "description": "Whether to tag the role in updates."},
            "refresh_interval": {"type": "int", "description": "Refresh interval in seconds."},
            "refresh_time": {"type": "str", "description": "Refresh time in military format (e.g., 1830)."},
            "time_zone": {"type": "str", "description": "Time zone for weather updates."},
            "show_footer": {"type": "bool", "description": "Whether to show the footer in embeds."},
        },
    )
