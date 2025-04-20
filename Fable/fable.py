from redbot.core import commands, Config
import discord
from typing import Optional, List
from Fable.google_sync_utils import (
    export_to_sheet, import_from_sheet, export_to_doc, import_from_doc
)
import importlib.util
import subprocess
import sys

async def ensure_google_apis():
    """
    Ensure google-api-python-client and google-auth are installed.
    """
    required = [
        ("googleapiclient", "google-api-python-client"),
        ("google.oauth2", "google-auth")
    ]
    for module, package in required:
        if importlib.util.find_spec(module) is None:
            subprocess.run([sys.executable, "-m", "pip", "install", package])

class Fable(commands.Cog):
    """A living world tracker for character-driven RP groups."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2025041901)
        default_guild = {
            "characters": {},
            "relationships": {},
            "logs": [],
            "lore": {},
            "mail": {},
            "sync": {},
            "settings": {},
            "backups": {},
            "mail_expiry_days": 30,
        }
        self.config.register_guild(**default_guild)

    async def cog_load(self):
        await ensure_google_apis()

    @commands.hybrid_group(name="fable", description="A living world tracker for character-driven RP groups.")
    async def fable(self, ctx: commands.Context):
        """Parent command for Fable RP tracker."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    # Character Profile System
    @fable.group(name="character", description="Manage RP character profiles.")
    async def character(self, ctx: commands.Context):
        """Character profile management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @character.command(name="create", description="Create a new character profile with traits and relationships.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def create(self, ctx: commands.Context, name: str, *, args: str):
        """
        Create a new character profile.
        
        Usage:
        [p]fable character create "Vex" "A cynical bard" --trait "Skilled musician" --ally @Mira
        """
        import argparse
        import shlex
        # Parse arguments for traits and relationships
        parser = argparse.ArgumentParser(prog="character_create", add_help=False)
        parser.add_argument("description", type=str)
        parser.add_argument("--trait", action="append", dest="traits", default=[])
        parser.add_argument("--ally", action="append", dest="allies", default=[])
        parser.add_argument("--rival", action="append", dest="rivals", default=[])
        parser.add_argument("--neutral", action="append", dest="neutrals", default=[])
        try:
            split_args = shlex.split(args)
            parsed = parser.parse_args(split_args)
        except Exception as e:
            await ctx.send_help(ctx.command)
            return
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        user_id = str(user.id)
        if name in characters:
            embed = discord.Embed(
                title="❌ Character Exists",
                description=f"A character named **{name}** already exists.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Build character profile
        character_data = {
            "name": name,
            "description": parsed.description,
            "owner_id": user_id,
            "traits": parsed.traits,
            "relationships": {
                "ally": parsed.allies,
                "rival": parsed.rivals,
                "neutral": parsed.neutrals
            }
        }
        characters[name] = character_data
        await self.config.guild(guild).characters.set(characters)
        # Build confirmation embed
        embed = discord.Embed(
            title=f"Character Created: {name}",
            description=parsed.description,
            color=0x43B581
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        if parsed.traits:
            embed.add_field(name="Traits", value="\n".join(f"• {t}" for t in parsed.traits), inline=False)
        rel_lines = []
        for rel_type, rel_list in character_data["relationships"].items():
            if rel_list:
                rel_lines.append(f"**{rel_type.capitalize()}s:** " + ", ".join(rel_list))
        if rel_lines:
            embed.add_field(name="Relationships", value="\n".join(rel_lines), inline=False)
        embed.set_footer(text="Fable RP Tracker", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="edit", description="Edit a character's description, trait, or relationship.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_edit(self, ctx: commands.Context, name: str, field: str, *, new_value: str):
        """
        Edit a character's description, trait, or relationship.
        
        Usage:
        [p]fable character edit "Vex" description "A new description"
        [p]fable character edit "Vex" trait "New Trait"
        [p]fable character edit "Vex" relationship "ally:@Mira"
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        character = characters.get(name)
        if not character:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{name}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == character["owner_id"]
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the character's owner or a server admin can edit this character.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        field = field.lower()
        updated = False
        if field == "description":
            character["description"] = new_value
            updated = True
        elif field == "trait":
            if "traits" not in character:
                character["traits"] = []
            if new_value not in character["traits"]:
                character["traits"].append(new_value)
                updated = True
        elif field == "relationship":
            # Format: type:@User or type:Name
            if ":" not in new_value:
                await ctx.send("Please specify relationship as type:target (e.g. ally:@Mira)")
                return
            rel_type, rel_target = new_value.split(":", 1)
            rel_type = rel_type.lower()
            if rel_type not in character["relationships"]:
                character["relationships"][rel_type] = []
            if rel_target not in character["relationships"][rel_type]:
                character["relationships"][rel_type].append(rel_target)
                updated = True
        else:
            await ctx.send("Unknown field. Use description, trait, or relationship.")
            return
        if updated:
            characters[name] = character
            await self.config.guild(guild).characters.set(characters)
            embed = discord.Embed(
                title="✅ Character Updated",
                description=f"**{name}**'s {field} updated.",
                color=0x43B581
            )
            embed.set_footer(text="Fable RP Tracker • Character Edit", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)
        else:
            await ctx.send("No changes made (may already exist).")

    @character.command(name="view", description="View a character profile.")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def character_view(self, ctx: commands.Context, name: str):
        """
        View a character profile by name.
        
        Usage:
        [p]fable character view "Vex"
        """
        guild = ctx.guild
        characters = await self.config.guild(guild).characters() or {}
        character = characters.get(name)
        if not character:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{name}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        owner = guild.get_member(int(character["owner_id"]))
        embed = discord.Embed(
            title=f"{character['name']}",
            description=character["description"],
            color=0x7289DA
        )
        if owner:
            embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        if character.get("traits"):
            embed.add_field(name="Traits", value="\n".join(f"• {t}" for t in character["traits"]), inline=False)
        rel_lines = []
        for rel_type, rel_list in character.get("relationships", {}).items():
            if rel_list:
                rel_lines.append(f"**{rel_type.capitalize()}s:** " + ", ".join(rel_list))
        if rel_lines:
            embed.add_field(name="Relationships", value="\n".join(rel_lines), inline=False)
        embed.set_footer(text="Fable RP Tracker • Character Profile", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="list", description="List all characters or those belonging to a user.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def character_list(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """
        List all characters in the server, or only those belonging to a specific user.
        
        Usage:
        [p]fable character list
        [p]fable character list @User
        """
        guild = ctx.guild
        characters = await self.config.guild(guild).characters() or {}
        if user:
            user_id = str(user.id)
            filtered = [c for c in characters.values() if c.get("owner_id") == user_id]
            title = f"Characters for {user.display_name}"
        else:
            filtered = list(characters.values())
            title = f"All Characters in {guild.name}"
        if not filtered:
            embed = discord.Embed(
                title="No Characters Found",
                description="No characters found for this query.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Paginate if more than 10 characters
        pages = [filtered[i:i+10] for i in range(0, len(filtered), 10)]
        for idx, page in enumerate(pages, 1):
            embed = discord.Embed(
                title=title + (f" (Page {idx}/{len(pages)})" if len(pages) > 1 else ""),
                color=0x7289DA
            )
            for char in page:
                owner = guild.get_member(int(char["owner_id"]))
                owner_name = owner.display_name if owner else f"<@{char['owner_id']}>"
                desc = char["description"]
                embed.add_field(
                    name=f"{char['name']} (by {owner_name})",
                    value=(desc[:100] + "..." if len(desc) > 100 else desc),
                    inline=False
                )
            embed.set_footer(text="Fable RP Tracker • Character List", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)

    @character.command(name="delete", description="Delete a character profile.")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def character_delete(self, ctx: commands.Context, name: str):
        """
        Delete a character profile by name. Only the owner or an admin can delete.
        
        Usage:
        [p]fable character delete "Vex"
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        character = characters.get(name)
        if not character:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{name}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == character["owner_id"]
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the character's owner or a server admin can delete this character.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        del characters[name]
        await self.config.guild(guild).characters.set(characters)
        embed = discord.Embed(
            title="🗑️ Character Deleted",
            description=f"The character **{name}** has been deleted.",
            color=0xFAA61A
        )
        embed.set_footer(text="Fable RP Tracker • Character Deleted", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @fable.command(name="relations", description="Show all relationships for a character.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relations(self, ctx: commands.Context, character: str):
        """
        Show all relationships for a character.
        
        Usage:
        [p]fable relations "Vex"
        """
        guild = ctx.guild
        characters = await self.config.guild(guild).characters() or {}
        char = characters.get(character)
        if not char:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{character}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        rels = char.get("relationships", {})
        if not any(rels.values()):
            embed = discord.Embed(
                title=f"Relationships for {character}",
                description="This character has no recorded relationships.",
                color=0xFAA61A
            )
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title=f"Relationships for {character}",
            color=0x7289DA
        )
        for rel_type, rel_list in rels.items():
            if rel_list:
                embed.add_field(
                    name=f"{rel_type.capitalize()}s",
                    value=", ".join(rel_list),
                    inline=False
                )
        embed.set_footer(text="Fable RP Tracker • Character Relationships", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    # Relationship Management
    @fable.group(name="relationship", description="Manage character relationships.")
    @commands.guild_only()
    async def relationship(self, ctx: commands.Context):
        """
        Relationship management commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @relationship.command(name="add", description="Add a relationship between two characters.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relationship_add(self, ctx: commands.Context, character1: str, character2: str, type: str, *, description: Optional[str] = None):
        """
        Add a relationship between two characters.
        Usage:
        [p]fable relationship add "Vex" "Mira" ally
        [p]fable relationship add "Vex" "Mira" rival "They compete for the same artifact."
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        char1 = characters.get(character1)
        char2 = characters.get(character2)
        if not char1 or not char2:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description="Both characters must exist to create a relationship.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == char1["owner_id"] or ctx.author.guild_permissions.administrator
        if not is_owner:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the owner of the first character or an admin can add relationships.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        rel_type = type.lower()
        if rel_type not in char1["relationships"]:
            char1["relationships"][rel_type] = []
        if character2 not in char1["relationships"][rel_type]:
            char1["relationships"][rel_type].append(character2)
        relationships = await self.config.guild(guild).relationships() or {}
        rel_key = f"{character1}|{character2}|{rel_type}"
        relationships[rel_key] = {
            "description": description or "",
            "created_by": str(user.id)
        }
        await self.config.guild(guild).relationships.set(relationships)
        characters[character1] = char1
        await self.config.guild(guild).characters.set(characters)
        embed = discord.Embed(
            title="Relationship Added",
            description=f"**{character1}** is now a **{rel_type}** of **{character2}**.",
            color=0x43B581
        )
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text="Fable RP Tracker • Relationship Added", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @relationship.command(name="edit", description="Edit a relationship's type or description.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relationship_edit(self, ctx: commands.Context, character1: str, character2: str, field: str, *, new_value: str):
        """
        Edit a relationship's type or description.
        Usage:
        [p]fable relationship edit "Vex" "Mira" type rival
        [p]fable relationship edit "Vex" "Mira" description "Now they're best friends."
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        relationships = await self.config.guild(guild).relationships() or {}
        char1 = characters.get(character1)
        char2 = characters.get(character2)
        if not char1 or not char2:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description="Both characters must exist to edit a relationship.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == char1["owner_id"] or ctx.author.guild_permissions.administrator
        if not is_owner:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the owner of the first character or an admin can edit relationships.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        rel_key = None
        for k in relationships:
            if k.startswith(f"{character1}|{character2}|"):
                rel_key = k
                break
        if not rel_key:
            embed = discord.Embed(
                title="❌ Relationship Not Found",
                description="No relationship found between these characters.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        if field.lower() == "type":
            _, _, old_type = rel_key.split("|", 2)
            new_key = f"{character1}|{character2}|{new_value.lower()}"
            relationships[new_key] = relationships.pop(rel_key)
            if old_type in char1["relationships"] and character2 in char1["relationships"][old_type]:
                char1["relationships"][old_type].remove(character2)
                if new_value.lower() not in char1["relationships"]:
                    char1["relationships"][new_value.lower()] = []
                char1["relationships"][new_value.lower()].append(character2)
            await self.config.guild(guild).relationships.set(relationships)
            characters[character1] = char1
            await self.config.guild(guild).characters.set(characters)
            embed = discord.Embed(
                title="Relationship Type Updated",
                description=f"**{character1}** and **{character2}** relationship type changed to **{new_value}**.",
                color=0x43B581
            )
            embed.set_footer(text="Fable RP Tracker • Relationship Edit", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)
        elif field.lower() == "description":
            relationships[rel_key]["description"] = new_value
            await self.config.guild(guild).relationships.set(relationships)
            embed = discord.Embed(
                title="Relationship Description Updated",
                description=f"Description updated for **{character1}** and **{character2}**.",
                color=0x43B581
            )
            embed.set_footer(text="Fable RP Tracker • Relationship Edit", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)
        else:
            await ctx.send("Unknown field. Use 'type' or 'description'.")

    @relationship.command(name="remove", description="Remove a relationship between two characters.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relationship_remove(self, ctx: commands.Context, character1: str, character2: str):
        """
        Remove a relationship between two characters.
        Usage:
        [p]fable relationship remove "Vex" "Mira"
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        relationships = await self.config.guild(guild).relationships() or {}
        char1 = characters.get(character1)
        char2 = characters.get(character2)
        if not char1 or not char2:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description="Both characters must exist to remove a relationship.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == char1["owner_id"] or ctx.author.guild_permissions.administrator
        if not is_owner:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the owner of the first character or an admin can remove relationships.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        found = False
        for rel_type, rel_list in char1["relationships"].items():
            if character2 in rel_list:
                rel_list.remove(character2)
                found = True
        to_remove = []
        for k in relationships:
            if k.startswith(f"{character1}|{character2}|"):
                to_remove.append(k)
        for k in to_remove:
            relationships.pop(k)
        if found:
            characters[character1] = char1
            await self.config.guild(guild).characters.set(characters)
            await self.config.guild(guild).relationships.set(relationships)
            embed = discord.Embed(
                title="Relationship Removed",
                description=f"Relationship between **{character1}** and **{character2}** has been removed.",
                color=0xFAA61A
            )
            embed.set_footer(text="Fable RP Tracker • Relationship Removed", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Relationship Not Found",
                description=f"No relationship found between **{character1}** and **{character2}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)

    # Event Timeline
    @fable.group(name="event", description="Log and manage in-character events.")
    async def event(self, ctx: commands.Context):
        """
        Event logging and management commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @event.command(name="log", description="Log an in-character event.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def event_log(self, ctx: commands.Context, characters: str, description: str, date: Optional[str] = None):
        """
        Log an in-character event.
        
        Usage:
        [p]fable event log "Vex, Mira" "Discovered the ancient tomb together" --date 3023-12-05
        """
        guild = ctx.guild
        user = ctx.author
        all_characters = await self.config.guild(guild).characters() or {}
        logs = await self.config.guild(guild).logs() or []
        # Split characters by comma and strip whitespace
        char_names = [c.strip() for c in characters.split(",") if c.strip()]
        involved = []
        missing = []
        for cname in char_names:
            if cname in all_characters:
                involved.append(cname)
            else:
                missing.append(cname)
        if not involved:
            embed = discord.Embed(
                title="❌ No Valid Characters",
                description="You must specify at least one valid character for the event.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        if missing:
            embed = discord.Embed(
                title="⚠️ Some Characters Not Found",
                description=f"The following characters do not exist and were skipped: {', '.join(missing)}",
                color=0xFAA61A
            )
            await ctx.send(embed=embed)
        event_id = len(logs) + 1
        event_data = {
            "id": event_id,
            "description": description,
            "ic_date": date or "Unspecified",
            "created_at": discord.utils.utcnow().isoformat(),
            "created_by": str(user.id),
            "characters": involved
        }
        logs.append(event_data)
        await self.config.guild(guild).logs.set(logs)
        embed = discord.Embed(
            title="Event Logged",
            description=description,
            color=0x43B581
        )
        embed.add_field(name="Characters", value=", ".join(involved), inline=False)
        embed.add_field(name="IC Date", value=event_data["ic_date"], inline=True)
        embed.add_field(name="Event ID", value=str(event_id), inline=True)
        embed.set_footer(text=f"Logged by {ctx.author.display_name} • Fable RP Tracker")
        await ctx.send(embed=embed)

    @event.command(name="edit", description="Edit an event's description.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def event_edit(self, ctx: commands.Context, event_id: int, *, new_description: str):
        """
        Edit an event's description by event ID.
        
        Usage:
        [p]fable event edit 3 "New event description"
        """
        guild = ctx.guild
        user = ctx.author
        logs = await self.config.guild(guild).logs() or []
        event = next((e for e in logs if e["id"] == event_id), None)
        if not event:
            embed = discord.Embed(
                title="❌ Event Not Found",
                description=f"No event with ID {event_id} exists.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_admin = ctx.author.guild_permissions.administrator
        is_owner = str(user.id) == event["created_by"]
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the event creator or a server admin can edit this event.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        event["description"] = new_description
        await self.config.guild(guild).logs.set(logs)
        embed = discord.Embed(
            title="Event Updated",
            description=f"Event {event_id} description updated.",
            color=0x43B581
        )
        embed.add_field(name="New Description", value=new_description, inline=False)
        embed.set_footer(text="Fable RP Tracker • Event Edit", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @event.command(name="delete", description="Delete an event.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def event_delete(self, ctx: commands.Context, event_id: int):
        """
        Delete an event by event ID.
        
        Usage:
        [p]fable event delete 3
        """
        guild = ctx.guild
        user = ctx.author
        logs = await self.config.guild(guild).logs() or []
        event = next((e for e in logs if e["id"] == event_id), None)
        if not event:
            embed = discord.Embed(
                title="❌ Event Not Found",
                description=f"No event with ID {event_id} exists.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_admin = ctx.author.guild_permissions.administrator
        is_owner = str(user.id) == event["created_by"]
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the event creator or a server admin can delete this event.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        logs = [e for e in logs if e["id"] != event_id]
        await self.config.guild(guild).logs.set(logs)
        embed = discord.Embed(
            title="🗑️ Event Deleted",
            description=f"Event {event_id} has been deleted.",
            color=0xFAA61A
        )
        embed.set_footer(text="Fable RP Tracker • Event Deleted", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @fable.group(name="timeline", description="View and search the event timeline.")
    async def timeline(self, ctx: commands.Context):
        """
        Timeline viewing and searching commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @timeline.command(name="recent", description="Show recent events.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def timeline_recent(self, ctx: commands.Context, number: Optional[int] = 5):
        """
        Show the most recent events in the timeline.
        
        Usage:
        [p]fable timeline recent 5
        """
        guild = ctx.guild
        logs = await self.config.guild(guild).logs() or []
        if not logs:
            embed = discord.Embed(
                title="No Events Found",
                description="There are no events logged yet.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Ensure number is an int and not None
        number = number if number is not None else 5
        number = max(1, min(int(number), 20))
        logs_sorted = sorted(logs, key=lambda e: e.get("created_at", ""), reverse=True)
        events = logs_sorted[:number]
        embed = discord.Embed(
            title=f"Recent Events (Last {number})",
            color=0x7289DA
        )
        for event in events:
            chars = ", ".join(event.get("characters", []))
            desc = event.get("description", "No description.")
            ic_date = event.get("ic_date", "Unspecified")
            eid = event.get("id", "?")
            embed.add_field(
                name=f"Event {eid} | {ic_date}",
                value=f"**Characters:** {chars}\n{desc}",
                inline=False
            )
        embed.set_footer(text="Fable RP Tracker • Timeline", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @timeline.command(name="search", description="Search the timeline for a keyword.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def timeline_search(self, ctx: commands.Context, keyword: str):
        """
        Search the timeline for a keyword in event descriptions.
        
        Usage:
        [p]fable timeline search tomb
        """
        guild = ctx.guild
        logs = await self.config.guild(guild).logs() or []
        results = [e for e in logs if keyword.lower() in e.get("description", "").lower()]
        if not results:
            embed = discord.Embed(
                title="No Events Found",
                description=f"No events found containing '{keyword}'.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title=f"Events Matching '{keyword}'",
            color=0x7289DA
        )
        for event in results[:10]:
            chars = ", ".join(event.get("characters", []))
            desc = event.get("description", "No description.")
            ic_date = event.get("ic_date", "Unspecified")
            eid = event.get("id", "?")
            embed.add_field(
                name=f"Event {eid} | {ic_date}",
                value=f"**Characters:** {chars}\n{desc}",
                inline=False
            )
        if len(results) > 10:
            embed.set_footer(text=f"Showing first 10 of {len(results)} results • Fable RP Tracker")
        else:
            embed.set_footer(text="Fable RP Tracker • Timeline Search", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    # Collaborative Lore System
    @fable.group(name="lore", description="Collaborative worldbuilding commands.")
    async def lore(self, ctx: commands.Context):
        """
        Lore collaboration commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @lore.command(name="suggest", description="Suggest a new lore entry.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lore_suggest(self, ctx: commands.Context, name: str, description: str, type: Optional[str] = None):
        """
        Suggest a new lore entry.
        """
        guild = ctx.guild
        user = ctx.author
        lore = await self.config.guild(guild).lore() or {}
        suggestions = lore.get("suggestions", {})
        approved = lore.get("approved", {})
        # Prevent duplicate names
        if name in suggestions or name in approved:
            embed = discord.Embed(
                title="❌ Lore Entry Exists",
                description=f"A lore entry named **{name}** already exists or is pending approval.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        entry_id = len(suggestions) + len(approved) + 1
        suggestions[name] = {
            "id": entry_id,
            "name": name,
            "description": description,
            "type": type or "Uncategorized",
            "suggested_by": str(user.id),
            "status": "pending",
            "timestamp": discord.utils.utcnow().isoformat()
        }
        lore["suggestions"] = suggestions
        await self.config.guild(guild).lore.set(lore)
        embed = discord.Embed(
            title="Lore Entry Suggested",
            description=f"**{name}** has been suggested and is pending approval.",
            color=0x43B581
        )
        embed.add_field(name="Type", value=type or "Uncategorized", inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text=f"Suggested by {ctx.author.display_name} • Fable RP Tracker")
        await ctx.send(embed=embed)

    @lore.command(name="approve", description="Approve a suggested lore entry.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def lore_approve(self, ctx: commands.Context, name: str):
        """
        Approve a suggested lore entry.
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        suggestions = lore.get("suggestions", {})
        approved = lore.get("approved", {})
        entry = suggestions.pop(name, None)
        if not entry:
            embed = discord.Embed(
                title="❌ Suggestion Not Found",
                description=f"No pending suggestion named **{name}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        entry["status"] = "approved"
        approved[name] = entry
        lore["suggestions"] = suggestions
        lore["approved"] = approved
        await self.config.guild(guild).lore.set(lore)
        embed = discord.Embed(
            title="Lore Entry Approved",
            description=f"**{name}** has been approved and added to the lore.",
            color=0x43B581
        )
        embed.add_field(name="Type", value=entry.get("type", "Uncategorized"), inline=True)
        embed.add_field(name="Description", value=entry.get("description", "No description."), inline=False)
        embed.set_footer(text=f"Approved by {ctx.author.display_name} • Fable RP Tracker")
        await ctx.send(embed=embed)

    @lore.command(name="deny", description="Deny a suggested lore entry.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def lore_deny(self, ctx: commands.Context, name: str):
        """
        Deny a suggested lore entry.
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        suggestions = lore.get("suggestions", {})
        entry = suggestions.pop(name, None)
        if not entry:
            embed = discord.Embed(
                title="❌ Suggestion Not Found",
                description=f"No pending suggestion named **{name}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        lore["suggestions"] = suggestions
        await self.config.guild(guild).lore.set(lore)
        embed = discord.Embed(
            title="Lore Entry Denied",
            description=f"The suggestion **{name}** has been denied and removed.",
            color=0xFAA61A
        )
        embed.set_footer(text=f"Denied by {ctx.author.display_name} • Fable RP Tracker")
        await ctx.send(embed=embed)

    @lore.command(name="edit", description="Edit a lore entry's description.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def lore_edit(self, ctx: commands.Context, name: str, new_description: str):
        """
        Edit a lore entry's description.
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        approved = lore.get("approved", {})
        entry = approved.get(name)
        if not entry:
            embed = discord.Embed(
                title="❌ Lore Entry Not Found",
                description=f"No approved lore entry named **{name}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        entry["description"] = new_description
        approved[name] = entry
        lore["approved"] = approved
        await self.config.guild(guild).lore.set(lore)
        embed = discord.Embed(
            title="Lore Entry Updated",
            description=f"**{name}**'s description has been updated.",
            color=0x43B581
        )
        embed.add_field(name="New Description", value=new_description, inline=False)
        embed.set_footer(text=f"Edited by {ctx.author.display_name} • Fable RP Tracker")
        await ctx.send(embed=embed)

    @lore.command(name="view", description="View a lore entry.")
    @commands.guild_only()
    async def lore_view(self, ctx: commands.Context, name: str):
        """
        View a lore entry.
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        approved = lore.get("approved", {})
        entry = approved.get(name)
        if not entry:
            embed = discord.Embed(
                title="❌ Lore Entry Not Found",
                description=f"No approved lore entry named **{name}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title=f"Lore: {entry['name']}",
            description=entry.get("description", "No description."),
            color=0x7289DA
        )
        embed.add_field(name="Type", value=entry.get("type", "Uncategorized"), inline=True)
        embed.add_field(name="Status", value=entry.get("status", "approved"), inline=True)
        suggester = ctx.guild.get_member(int(entry.get("suggested_by", 0)))
        if suggester:
            embed.set_footer(text=f"Suggested by {suggester.display_name} • Fable RP Tracker")
        else:
            embed.set_footer(text="Fable RP Tracker • Lore View", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @lore.command(name="list", description="List all lore entries, optionally filtered by type.")
    @commands.guild_only()
    async def lore_list(self, ctx: commands.Context, type: Optional[str] = None):
        """
        List all lore entries, optionally filtered by type.
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        approved = lore.get("approved", {})
        entries = list(approved.values())
        if type:
            entries = [e for e in entries if e.get("type", "Uncategorized").lower() == type.lower()]
        if not entries:
            embed = discord.Embed(
                title="No Lore Entries Found",
                description="No lore entries found for the given filter.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Paginate if more than 10 entries
        pages = [entries[i:i+10] for i in range(0, len(entries), 10)]
        for idx, page in enumerate(pages, 1):
            embed = discord.Embed(
                title=f"Lore Entries (Page {idx}/{len(pages)})",
                color=0x7289DA
            )
            for entry in page:
                embed.add_field(
                    name=f"{entry['name']} [{entry.get('type', 'Uncategorized')}]",
                    value=(entry.get("description", "No description.")[:100] + "..." if len(entry.get("description", "")) > 100 else entry.get("description", "No description.")),
                    inline=False
                )
            embed.set_footer(text="Fable RP Tracker • Lore List", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)

    @lore.command(name="search", description="Search lore entries by keyword.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def lore_search(self, ctx: commands.Context, keyword: str):
        """
        Search lore entries by keyword.
        
        Usage:
        [p]fable lore search dragon
        """
        guild = ctx.guild
        lore = await self.config.guild(guild).lore() or {}
        approved = lore.get("approved", {})
        results = [e for e in approved.values() if keyword.lower() in e.get("description", "").lower()]
        if not results:
            embed = discord.Embed(
                title="No Lore Entries Found",
                description=f"No lore entries found containing '{keyword}'.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title=f"Lore Entries Matching '{keyword}'",
            color=0x7289DA
        )
        for entry in results[:10]:
            embed.add_field(
                name=f"{entry['name']} [{entry.get('type', 'Uncategorized')}]",
                value=(entry.get("description", "No description.")[:100] + "..." if len(entry.get("description", "")) > 100 else entry.get("description", "No description.")),
                inline=False
            )
        if len(results) > 10:
            embed.set_footer(text=f"Showing first 10 of {len(results)} results • Fable RP Tracker")
        else:
            embed.set_footer(text="Fable RP Tracker • Lore Search", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    # IC Mail System
    @fable.group(name="mail", description="In-character mail system.")
    async def mail(self, ctx: commands.Context):
        """
        In-character mail system commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @mail.command(name="send", description="Send IC mail to a recipient character.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mail_send(self, ctx: commands.Context, recipient: str, message: str, from_character: Optional[str] = None):
        """
        Send IC mail to a recipient character. Supports file attachments.
        Notifies the character's owner via DM if possible.
        Usage:
        [p]fable mail send "Vex" "Hello!" --from_character "Mira"
        """
        await self._prune_expired_mail(ctx.guild)
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        mail = await self.config.guild(guild).mail() or {}
        allowed_types = await self.config.guild(guild).mail_allowed_attachment_types() or ["png", "jpg", "jpeg", "gif", "pdf"]
        # Validate recipient
        if recipient not in characters:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{recipient}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Validate sender character if provided
        if from_character and from_character not in characters:
            embed = discord.Embed(
                title="❌ Sender Character Not Found",
                description=f"No character named **{from_character}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Handle attachments with type restrictions
        attachment_urls = []
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                ext = attachment.filename.split(".")[-1].lower()
                if ext not in allowed_types:
                    embed = discord.Embed(
                        title="❌ Attachment Type Not Allowed",
                        description=f"Attachment `{attachment.filename}` is not an allowed type. Allowed: {', '.join(allowed_types)}",
                        color=0xF04747
                    )
                    await ctx.send(embed=embed)
                    return
                attachment_urls.append(attachment.url)
        # Prepare mail entry
        recipient_mail = mail.get(recipient, [])
        mail_id = len(recipient_mail) + 1
        mail_entry = {
            "id": mail_id,
            "from": from_character or user.display_name,
            "from_user_id": str(user.id),
            "message": message,
            "timestamp": discord.utils.utcnow().isoformat(),
            "read": False,
            "attachments": attachment_urls
        }
        recipient_mail.append(mail_entry)
        mail[recipient] = recipient_mail
        await self.config.guild(guild).mail.set(mail)
        embed = discord.Embed(
            title="📨 Mail Sent",
            description=f"Mail sent to **{recipient}**.",
            color=0x43B581
        )
        embed.add_field(name="From", value=mail_entry["from"], inline=True)
        embed.add_field(name="Message", value=message, inline=False)
        if attachment_urls:
            embed.add_field(name="Attachments", value="\n".join(attachment_urls), inline=False)
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)
        # Notify recipient owner via DM
        owner_id = characters[recipient]["owner_id"]
        owner = guild.get_member(int(owner_id))
        if owner:
            try:
                notify_embed = discord.Embed(
                    title=f"📬 New Mail for {recipient}",
                    description=message,
                    color=0x43B581
                )
                notify_embed.add_field(name="From", value=mail_entry["from"], inline=True)
                if attachment_urls:
                    notify_embed.add_field(name="Attachments", value="\n".join(attachment_urls), inline=False)
                notify_embed.set_footer(text=f"Sent in {guild.name}")
                await owner.send(embed=notify_embed)
            except Exception:
                # DM failed, fallback to notifying in server or configured channel
                channel_id = await self.config.guild(guild).mail_notification_channel()
                channel = guild.get_channel(channel_id) if channel_id else ctx.channel
                fallback_embed = discord.Embed(
                    title=f"📬 {recipient} received new mail!",
                    description=f"{recipient} has new mail from {mail_entry['from']}.",
                    color=0xFAA61A
                )
                await channel.send(embed=fallback_embed)

    @mail.command(name="read", description="Read IC mail (all or unread) for a character.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mail_read(self, ctx: commands.Context, character: str, filter: Optional[str] = "unread"):
        """
        Read IC mail (all or unread) for a character. Shows attachments if present.
        Usage:
        [p]fable mail read "Vex" unread
        [p]fable mail read "Vex" all
        """
        await self._prune_expired_mail(ctx.guild)
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        mail = await self.config.guild(guild).mail() or {}
        # Validate character
        if character not in characters:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{character}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Only allow owner or admin to read
        is_owner = str(user.id) == characters[character]["owner_id"]
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the character's owner or a server admin can read this mail.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        char_mail = mail.get(character, [])
        if filter == "unread":
            filtered_mail = [m for m in char_mail if not m.get("read", False)]
        else:
            filtered_mail = char_mail
        if not filtered_mail:
            embed = discord.Embed(
                title="No Mail Found",
                description=f"No {'unread' if filter == 'unread' else ''} mail found for **{character}**.",
                color=0xFAA61A
            )
            await ctx.send(embed=embed)
            return
        # Paginate if more than 5
        pages = [filtered_mail[i:i+5] for i in range(0, len(filtered_mail), 5)]
        for idx, page in enumerate(pages, 1):
            embed = discord.Embed(
                title=f"Mail for {character} (Page {idx}/{len(pages)})",
                color=0x7289DA
            )
            for mail_entry in page:
                value = (mail_entry['message'][:100] + "..." if len(mail_entry['message']) > 100 else mail_entry['message'])
                if mail_entry.get("attachments"):
                    value += f"\n[Attachments] " + " | ".join(mail_entry["attachments"])
                embed.add_field(
                    name=f"Mail #{mail_entry['id']} from {mail_entry['from']}",
                    value=value,
                    inline=False
                )
            embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)

    @mail.command(name="view", description="View a specific mail message by ID.")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def mail_view(self, ctx: commands.Context, character: str, mail_id: int):
        """
        View a specific mail message by ID (marks as read). Shows attachments if present.
        Usage:
        [p]fable mail view "Vex" 2
        """
        await self._prune_expired_mail(ctx.guild)
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        mail = await self.config.guild(guild).mail() or {}
        if character not in characters:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{character}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == characters[character]["owner_id"]
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the character's owner or a server admin can view this mail.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        char_mail = mail.get(character, [])
        mail_entry = next((m for m in char_mail if m["id"] == mail_id), None)
        if not mail_entry:
            embed = discord.Embed(
                title="Mail Not Found",
                description=f"No mail with ID {mail_id} found for **{character}**.",
                color=0xFAA61A
            )
            await ctx.send(embed=embed)
            return
        mail_entry["read"] = True
        await self.config.guild(guild).mail.set(mail)
        embed = discord.Embed(
            title=f"Mail #{mail_id} for {character}",
            description=mail_entry["message"],
            color=0x7289DA
        )
        embed.add_field(name="From", value=mail_entry["from"], inline=True)
        embed.add_field(name="Sent", value=mail_entry["timestamp"], inline=True)
        if mail_entry.get("attachments"):
            embed.add_field(name="Attachments", value="\n".join(mail_entry["attachments"]), inline=False)
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @mail.command(name="delete", description="Delete a mail message by ID.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mail_delete(self, ctx: commands.Context, character: str, mail_id: int):
        """
        Delete a mail message by ID.
        
        Usage:
        [p]fable mail delete "Vex" 2
        """
        await self._prune_expired_mail(ctx.guild)
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters() or {}
        mail = await self.config.guild(guild).mail() or {}
        if character not in characters:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{character}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        is_owner = str(user.id) == characters[character]["owner_id"]
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_owner or is_admin):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the character's owner or a server admin can delete this mail.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        char_mail = mail.get(character, [])
        mail_entry = next((m for m in char_mail if m["id"] == mail_id), None)
        if not mail_entry:
            embed = discord.Embed(
                title="Mail Not Found",
                description=f"No mail with ID {mail_id} found for **{character}**.",
                color=0xFAA61A
            )
            await ctx.send(embed=embed)
            return
        char_mail = [m for m in char_mail if m["id"] != mail_id]
        # Re-number mail IDs for this character
        for idx, m in enumerate(char_mail, 1):
            m["id"] = idx
        mail[character] = char_mail
        await self.config.guild(guild).mail.set(mail)
        embed = discord.Embed(
            title="🗑️ Mail Deleted",
            description=f"Mail #{mail_id} for **{character}** has been deleted.",
            color=0xFAA61A
        )
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @mail.command(name="setexpiry", description="Set mail auto-delete time in days (server owner/admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mail_setexpiry(self, ctx: commands.Context, days: int):
        """
        Set the number of days after which mail is auto-deleted.
        Only server owner or admins can use this.
        Usage: [p]fable mail setexpiry 14
        """
        if days < 1 or days > 365:
            embed = discord.Embed(
                title="❌ Invalid Expiry",
                description="Please choose a value between 1 and 365 days.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        await self.config.guild(ctx.guild).mail_expiry_days.set(days)
        embed = discord.Embed(
            title="Mail Expiry Updated",
            description=f"Mail will now be auto-deleted after {days} days.",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @mail.command(name="setnotifychannel", description="Set the fallback channel for mail notifications (admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mail_setnotifychannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Set the fallback channel for mail notifications if DMs fail.
        Only server admins can use this.
        Usage: [p]fable mail setnotifychannel #channel
        """
        await self.config.guild(ctx.guild).mail_notification_channel.set(channel.id)
        embed = discord.Embed(
            title="Mail Notification Channel Set",
            description=f"Mail notifications will be sent to {channel.mention} if DMs fail.",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @mail.command(name="setallowedtypes", description="Set allowed attachment types for mail (admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def mail_setallowedtypes(self, ctx: commands.Context, *, types: str):
        """
        Set allowed attachment file extensions for mail (comma-separated, e.g. png,jpg,pdf).
        Only server admins can use this.
        Usage: [p]fable mail setallowedtypes png,jpg,pdf
        """
        allowed = [t.strip().lower() for t in types.split(",") if t.strip()]
        if not allowed:
            embed = discord.Embed(
                title="❌ Invalid Types",
                description="You must specify at least one file extension.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        await self.config.guild(ctx.guild).mail_allowed_attachment_types.set(allowed)
        embed = discord.Embed(
            title="Allowed Attachment Types Set",
            description=f"Mail attachments are now limited to: {', '.join(allowed)}",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Mail System", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    async def _prune_expired_mail(self, guild: discord.Guild) -> None:
        """
        Remove expired mail for all characters in the guild based on mail_expiry_days setting.
        """
        import datetime
        mail = await self.config.guild(guild).mail() or {}
        expiry_days = await self.config.guild(guild).mail_expiry_days()
        if not expiry_days or expiry_days <= 0:
            return
        now = discord.utils.utcnow()
        changed = False
        for character, char_mail in mail.items():
            filtered = [m for m in char_mail if (now - datetime.datetime.fromisoformat(m["timestamp"])) < datetime.timedelta(days=expiry_days)]
            if len(filtered) != len(char_mail):
                # Re-number mail IDs
                for idx, m in enumerate(filtered, 1):
                    m["id"] = idx
                mail[character] = filtered
                changed = True
        if changed:
            await self.config.guild(guild).mail.set(mail)

    # Administrative Commands
    @fable.command(name="setup", description="Run the Fable setup wizard.")
    async def setup_cmd(self, ctx: commands.Context):
        """
        Run the Fable setup wizard.
        """
        await ctx.send("Setup wizard not yet implemented.")

    @fable.command(name="settings", description="View Fable settings for this server.")
    @commands.guild_only()
    async def settings(self, ctx: commands.Context):
        """
        View all Fable settings for this server in a detailed embed.
        """
        guild = ctx.guild
        config = await self.config.guild(guild).all()
        mail_expiry = config.get("mail_expiry_days", 30)
        allowed_types = config.get("mail_allowed_attachment_types", ["png", "jpg", "jpeg", "gif", "pdf"])
        notify_channel_id = config.get("mail_notification_channel")
        notify_channel = guild.get_channel(notify_channel_id) if notify_channel_id else None
        embed = discord.Embed(
            title=f"Fable Settings for {guild.name}",
            color=0x7289DA
        )
        embed.add_field(name="Mail Expiry (days)", value=str(mail_expiry), inline=True)
        embed.add_field(name="Allowed Attachment Types", value=", ".join(allowed_types), inline=True)
        embed.add_field(name="Notification Channel", value=notify_channel.mention if notify_channel else "Not set", inline=True)
        embed.add_field(name="Character Count", value=str(len(config.get("characters", {}))), inline=True)
        embed.add_field(name="Lore Entries", value=str(len(config.get("lore", {}).get("approved", {}))), inline=True)
        embed.add_field(name="Event Logs", value=str(len(config.get("logs", []))), inline=True)
        embed.set_footer(text="Fable RP Tracker • Settings", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @fable.command(name="backup", description="Create a backup of Fable data.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx: commands.Context):
        """
        Create a backup of all Fable data for this server as a downloadable JSON file.
        Only server admins can use this command.
        """
        import io
        import json
        guild = ctx.guild
        config = await self.config.guild(guild).all()
        data = json.dumps(config, indent=2)
        file = discord.File(io.BytesIO(data.encode()), filename=f"fable-backup-{guild.id}.json")
        embed = discord.Embed(
            title="Fable Backup Created",
            description="Your Fable data has been exported. Keep this file safe!",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Backup", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed, file=file)

    @fable.command(name="restore", description="Restore Fable data from a backup file.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def restore(self, ctx: commands.Context):
        """
        Restore Fable data from a backup JSON file. Only server admins can use this command.
        Upload the backup file as an attachment when running this command.
        """
        import json
        if not ctx.message.attachments:
            embed = discord.Embed(
                title="❌ No File Provided",
                description="Please upload a backup JSON file as an attachment.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        attachment = ctx.message.attachments[0]
        try:
            data = await attachment.read()
            config = json.loads(data.decode())
        except Exception:
            embed = discord.Embed(
                title="❌ Invalid File",
                description="Could not read or parse the backup file. Ensure it is a valid Fable backup JSON.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Confirm overwrite
        confirm_embed = discord.Embed(
            title="Restore Confirmation",
            description="This will overwrite all current Fable data for this server. Type `confirm` to proceed.",
            color=0xFAA61A
        )
        await ctx.send(embed=confirm_embed)
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
        try:
            reply = await ctx.bot.wait_for("message", check=check, timeout=30)
        except Exception:
            await ctx.send("Restore cancelled (no confirmation received).")
            return
        await self.config.guild(ctx.guild).set(config)
        embed = discord.Embed(
            title="Fable Data Restored",
            description="Fable data has been restored from the backup.",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Restore", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @fable.command(name="permissions", description="Set Fable permissions for a role.")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def permissions(self, ctx: commands.Context, role: discord.Role, permission_level: str):
        """
        Set Fable permissions for a role.

        Parameters
        ----------
        role : discord.Role
            The Discord role to set permissions for
        permission_level : str
            The permission level (e.g. 'admin', 'mod', 'user')
        """
        valid_levels = ["admin", "mod", "user"]
        level = permission_level.lower()
        if level not in valid_levels:
            embed = discord.Embed(
                title="❌ Invalid Permission Level",
                description=f"Permission level must be one of: {', '.join(valid_levels)}.",
                color=0xF04747
            )
            embed.set_footer(text="Fable RP Tracker • Permissions", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
            await ctx.send(embed=embed)
            return
        permissions = await self.config.guild(ctx.guild).settings() or {}
        if "role_permissions" not in permissions:
            permissions["role_permissions"] = {}
        permissions["role_permissions"][str(role.id)] = level
        await self.config.guild(ctx.guild).settings.set(permissions)
        embed = discord.Embed(
            title="Permissions Updated",
            description=f"Role {role.mention} set to **{level}** permissions.",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Permissions", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    async def cog_unload(self):
        """Cleanup tasks when the cog is unloaded."""
        pass

    # Character command aliases for direct access (e.g. [p]fable charlist)
    @commands.hybrid_command(name="charlist", description="List all characters or those belonging to a user.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def charlist(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """
        List all characters in the server, or only those belonging to a specific user.
        Usage:
        [p]fable charlist
        [p]fable charlist @User
        """
        await ctx.invoke(self.character_list, user=user)

    @commands.hybrid_command(name="chardelete", description="Delete a character profile.")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def chardelete(self, ctx: commands.Context, name: str):
        """
        Delete a character profile by name. Only the owner or an admin can delete.
        Usage:
        [p]fable chardelete "Vex"
        """
        await ctx.invoke(self.character_delete, name=name)

    @commands.hybrid_command(name="charview", description="View a character profile.")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def charview(self, ctx: commands.Context, name: str):
        """
        View a character profile by name.
        Usage:
        [p]fable charview "Vex"
        """
        await ctx.invoke(self.character_view, name=name)

    @commands.hybrid_command(name="charcreate", description="Create a new character profile with traits and relationships.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def charcreate(self, ctx: commands.Context, name: str, *, args: str):
        """
        Create a new character profile.
        Usage:
        [p]fable charcreate "Vex" "A cynical bard" --trait "Skilled musician" --ally @Mira
        """
        await ctx.invoke(self.create, name=name, args=args)

    @commands.hybrid_command(name="charedit", description="Edit a character's description, trait, or relationship.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def charedit(self, ctx: commands.Context, name: str, field: str, *, new_value: str):
        """
        Edit a character's description, trait, or relationship.
        Usage:
        [p]fable charedit "Vex" description "A new description"
        [p]fable charedit "Vex" trait "New Trait"
        [p]fable charedit "Vex" relationship "ally:@Mira"
        """
        await ctx.invoke(self.character_edit, name=name, field=field, new_value=new_value)

    @fable.command(name="sysetup", description="Set up Google sync (Sheet or Doc).")
    async def sysetup(self, ctx: commands.Context, source_type: str, url_or_id: str, api_key: str):
        """
        Set up Google sync for this server. Supports Google Sheets or Docs.
        Usage:
        [p]fable sysetup sheet <sheet_id> <api_key>
        [p]fable sysetup doc <doc_id> <api_key>
        """
        source_type = source_type.lower()
        if source_type not in ("sheet", "doc"):
            await ctx.send("Source type must be 'sheet' or 'doc'.")
            return
        sync = {
            "type": source_type,
            "id": url_or_id,
            "api_key": api_key
        }
        await self.config.guild(ctx.guild).sync.set(sync)
        embed = discord.Embed(
            title="Google Sync Setup Complete",
            description=f"Sync type: **{source_type}**\nID: `{url_or_id}`",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Sync Setup")
        await ctx.send(embed=embed)

    @fable.command(name="syexport", description="Export data to Google Sheets or Docs.")
    async def syexport(self, ctx: commands.Context, data_type: Optional[str] = None):
        """
        Export Fable data to Google Sheets or Docs.
        Usage: [p]fable syexport [data_type]
        """
        sync = await self.config.guild(ctx.guild).sync() or {}
        if not sync:
            await ctx.send("Sync is not set up. Use [p]fable sysetup first.")
            return
        data_type = data_type or "all"
        data = awaitself.config.guild(ctx.guild).all()
        if data_type != "all":
            data = data.get(data_type, {})
        try:
            if sync["type"] == "sheet":
                export_to_sheet(sync["id"], sync["api_key"], data)
                msg = f"Exported data to Google Sheet: `{sync['id']}`."
            else:
                export_to_doc(sync["id"], sync["api_key"], data)
                msg = f"Exported data to Google Doc: `{sync['id']}`."
            color = 0x43B581
        except Exception as e:
            msg = f"❌ Export failed: {e}"
            color = 0xF04747
        embed = discord.Embed(
            title="Sync Export",
            description=msg,
            color=color
        )
        embed.set_footer(text="Fable RP Tracker • Sync Export")
        await ctx.send(embed=embed)

    @fable.command(name="syimport", description="Import data from Google Sheets or Docs.")
    async def syimport(self, ctx: commands.Context, data_type: Optional[str] = None):
        """
        Import Fable data from Google Sheets or Docs.
        Usage: [p]fable syimport [data_type]
        """
        sync = await self.config.guild(ctx.guild).sync() or {}
        if not sync:
            await ctx.send("Sync is not set up. Use [p]fable sysetup first.")
            return
        try:
            if sync["type"] == "sheet":
                imported = import_from_sheet(sync["id"], sync["api_key"])
            else:
                imported = import_from_doc(sync["id"], sync["api_key"])
            if not imported:
                raise Exception("No data found or invalid format.")
            if data_type and data_type != "all":
                await self.config.guild(ctx.guild).set_raw(data_type, value=imported)
            else:
                await self.config.guild(ctx.guild).set(imported)
            msg = f"Imported data from Google {sync['type'].capitalize()}: `{sync['id']}`."
            color = 0x43B581
        except Exception as e:
            msg = f"❌ Import failed: {e}"
            color = 0xF04747
        embed = discord.Embed(
            title="Sync Import",
            description=msg,
            color=color
        )
        embed.set_footer(text="Fable RP Tracker • Sync Import")
        await ctx.send(embed=embed)

    @fable.command(name="systatus", description="Show Google sync status.")
    async def systatus(self, ctx: commands.Context):
        """
        Show the current Google sync configuration for this server.
        """
        sync = await self.config.guild(ctx.guild).sync() or {}
        if not sync:
            await ctx.send("Sync is not set up. Use [p]fable sysetup first.")
            return
        embed = discord.Embed(
            title="Google Sync Status",
            description=f"Type: **{sync.get('type','?')}**\nID: `{sync.get('id','?')}`",
            color=0x7289DA
        )
        embed.set_footer(text="Fable RP Tracker • Sync Status")
        await ctx.send(embed=embed)

    @fable.command(name="googlehelp", description="Show Google API setup instructions for Fable's sync features.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def googlehelp(self, ctx: commands.Context):
        """
        Display a step-by-step guide for setting up Google API credentials for Fable's sync features.
        """
        embed = discord.Embed(
            title="🛠️ Google API Setup Guide",
            description=(
                "To use Google Sheets/Docs sync, you must set up a Google Cloud service account and provide its key.\n\n"
                "**Steps:**\n"
                "1. Create a Google Cloud Project\n"
                "2. Enable Google Sheets & Docs APIs\n"
                "3. Create a Service Account\n"
                "4. Download a JSON key\n"
                "5. Add the key to Fable using `/fable setapikey` or the command below.\n\n"
                "See the full guide in the cog folder: `GOOGLE_API_SETUP.md`"
            ),
            color=0x7289DA
        )
        embed.add_field(
            name="Quick Start",
            value="[Google Cloud Console](https://console.cloud.google.com/)\n[Full Docs](https://cloud.google.com/iam/docs/creating-managing-service-account-keys)",
            inline=False
        )
        embed.set_footer(text="Fable RP Tracker • Google API", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        # Show current key status
        key = await self.config.guild(ctx.guild).settings.get_raw("google_api_key", default=None)
        if key:
            embed.add_field(name="Current API Key", value="✅ Set for this server.", inline=False)
        else:
            embed.add_field(name="Current API Key", value="❌ Not set. Use `/fable setapikey`.", inline=False)
        await ctx.send(embed=embed)

    @fable.command(name="setapikey", description="Set or update the Google API service account key for this server.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def setapikey(self, ctx: commands.Context, *, apikey: str):
        """
        Store your Google service account JSON key for this server.

        Parameters
        ----------
        apikey : str
            The full JSON string of your Google service account key.
        """
        try:
            import json
            json.loads(apikey)
        except Exception:
            await ctx.send("❌ That doesn't look like a valid JSON key. Please paste the full JSON string.")
            return
        await self.config.guild(ctx.guild).settings.set_raw("google_api_key", value=apikey)
        embed = discord.Embed(
            title="✅ Google API Key Set",
            description="Your Google service account key has been securely saved for this server.",
            color=0x43B581
        )
        embed.set_footer(text="Fable RP Tracker • Google API", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        # Show current key status
        embed.add_field(name="Current API Key", value="✅ Set for this server.", inline=False)
        await ctx.send(embed=embed)

    @fable.command(name="showapikey", description="Show if a Google API key is set for this server.")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def showapikey(self, ctx: commands.Context):
        """
        Show whether a Google API key is configured for this server.
        """
        key = await self.config.guild(ctx.guild).settings.get_raw("google_api_key", default=None)
        if key:
            msg = "✅ A Google API key is set for this server."
            color = 0x43B581
        else:
            msg = "❌ No Google API key is set. Use `/fable setapikey` to add one."
            color = 0xF04747
        embed = discord.Embed(title="Google API Key Status", description=msg, color=color)
        embed.set_footer(text="Fable RP Tracker • Google API", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        # Show current key status
        if key:
            embed.add_field(name="Current API Key", value="✅ Set for this server.", inline=False)
        else:
            embed.add_field(name="Current API Key", value="❌ Not set. Use `/fable setapikey`.", inline=False)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fable(bot))
