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

    @character.command(name="fields", description="Show all available character fields you can set.")
    async def character_fields(self, ctx: commands.Context):
        """
        Show all available fields you can set for a character profile.
        Usage: [p]fable character fields
        """
        fields = [
            ("name", "The character's name (required)"),
            ("description", "A detailed description (required)"),
            ("traits", "One or more personality traits (optional, use --trait)"),
            ("age", "The character's age (optional)"),
            ("species", "The character's species/race (optional)"),
            ("occupation", "The character's job or role (optional)"),
            ("relationships", "Allies, rivals, and neutrals (optional, use --ally, --rival, --neutral)")
        ]
        embed = discord.Embed(
            title="Available Character Fields",
            color=0x7289DA
        )
        for fname, fdesc in fields:
            embed.add_field(name=fname.capitalize(), value=fdesc, inline=False)
        embed.set_footer(text="Fable RP Tracker • Character Fields", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="create", description="Create a new character profile with traits and relationships.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def create(self, ctx: commands.Context, name: str, *, args: str):
        """
        Create a new character profile.
        Usage:
        [p]fable character create "Vex" "A cynical bard" --trait "Skilled musician" --ally @Mira --age 25 --species Elf --occupation Bard
        """
        import argparse
        import shlex
        parser = argparse.ArgumentParser(prog="character_create", add_help=False)
        parser.add_argument("description", type=str)
        parser.add_argument("--trait", action="append", dest="traits", default=[])
        parser.add_argument("--ally", action="append", dest="allies", default=[])
        parser.add_argument("--rival", action="append", dest="rivals", default=[])
        parser.add_argument("--neutral", action="append", dest="neutrals", default=[])
        parser.add_argument("--age", type=str, default=None)
        parser.add_argument("--species", type=str, default=None)
        parser.add_argument("--occupation", type=str, default=None)
        try:
            split_args = shlex.split(args)
            parsed = parser.parse_args(split_args)
        except Exception:
            await ctx.send_help(ctx.command)
            return
        guild = ctx.guild
        user = ctx.author
        user_id = str(user.id)
        existing = await self.config.guild(guild).characters.get_raw(name, default=None)
        if existing:
            embed = discord.Embed(
                title="❌ Character Exists",
                description=f"A character named **{name}** already exists.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        character_data = {
            "name": name,
            "description": parsed.description,
            "owner_id": user_id,
            "traits": parsed.traits,
            "age": parsed.age,
            "species": parsed.species,
            "occupation": parsed.occupation,
            "relationships": {
                "ally": parsed.allies,
                "rival": parsed.rivals,
                "neutral": parsed.neutrals
            }
        }
        await self.config.guild(guild).characters.set_raw(name, value=character_data)
        embed = discord.Embed(
            title=f"Character Created: {name}",
            description=parsed.description,
            color=0x43B581
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        if parsed.traits:
            embed.add_field(name="Traits", value="\n".join(f"• {t}" for t in parsed.traits), inline=False)
        if parsed.age:
            embed.add_field(name="Age", value=parsed.age, inline=True)
        if parsed.species:
            embed.add_field(name="Species", value=parsed.species, inline=True)
        if parsed.occupation:
            embed.add_field(name="Occupation", value=parsed.occupation, inline=True)
        rel_lines = []
        for rel_type, rel_list in character_data["relationships"].items():
            if rel_list:
                rel_lines.append(f"**{rel_type.capitalize()}s:** " + ", ".join(rel_list))
        if rel_lines:
            embed.add_field(name="Relationships", value="\n".join(rel_lines), inline=False)
        embed.set_footer(text="Fable RP Tracker", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="edit", description="Edit a character's description, trait, relationship, age, species, or occupation.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_edit(self, ctx: commands.Context, name: str, field: str, *, new_value: str):
        """
        Edit a character's description, trait, relationship, age, species, or occupation.
        Usage:
        [p]fable character edit "Vex" description "A new description"
        [p]fable character edit "Vex" trait "New Trait"
        [p]fable character edit "Vex" relationship "ally:@Mira"
        [p]fable character edit "Vex" age 30
        [p]fable character edit "Vex" species Elf
        [p]fable character edit "Vex" occupation Bard
        """
        guild = ctx.guild
        user = ctx.author
        character = await self.config.guild(guild).characters.get_raw(name, default=None)
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
        elif field in ("age", "species", "occupation"):
            character[field] = new_value
            updated = True
        else:
            await ctx.send("Unknown field. Use description, trait, relationship, age, species, or occupation.")
            return
        if updated:
            await self.config.guild(guild).characters.set_raw(name, value=character)
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
        character = await self.config.guild(guild).characters.get_raw(name, default=None)
        if not character:
            embed = discord.Embed(
                title="❌ Character Not Found",
                description=f"No character named **{name}** exists in this server.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        owner = guild.get_member(int(character["owner_id"]))
        description = character["description"]
        max_length = 4096
        embed = discord.Embed(
            title=f"{character['name']}",
            description=description[:max_length],
            color=0x7289DA
        )
        if owner:
            embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        if character.get("traits"):
            embed.add_field(name="Traits", value="\n".join(f"• {t}" for t in character["traits"]), inline=False)
        if character.get("age"):
            embed.add_field(name="Age", value=character["age"], inline=True)
        if character.get("species"):
            embed.add_field(name="Species", value=character["species"], inline=True)
        if character.get("occupation"):
            embed.add_field(name="Occupation", value=character["occupation"], inline=True)
        rel_lines = []
        for rel_type, rel_list in character.get("relationships", {}).items():
            if rel_list:
                rel_lines.append(f"**{rel_type.capitalize()}s:** " + ", ".join(rel_list))
        if rel_lines:
            embed.add_field(name="Relationships", value="\n".join(rel_lines), inline=False)
        embed.set_footer(text="Fable RP Tracker • Character Profile", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)
        if len(description) > max_length:
            import io
            file = discord.File(fp=io.BytesIO(description.encode("utf-8")), filename=f"{name}_description.txt")
            await ctx.send(content=f"Full description for **{name}** (continued):", file=file)

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
        all_names = await self.config.guild(guild).characters.get_attr("").get_raw()
        filtered = []
        if user:
            user_id = str(user.id)
            for name in all_names:
                char = await self.config.guild(guild).characters.get_raw(name, default=None)
                if char and char.get("owner_id") == user_id:
                    filtered.append(char)
            title = f"Characters for {user.display_name}"
        else:
            for name in all_names:
                char = await self.config.guild(guild).characters.get_raw(name, default=None)
                if char:
                    filtered.append(char)
            title = f"All Characters in {guild.name}"
        if not filtered:
            embed = discord.Embed(
                title="No Characters Found",
                description="No characters found for this query.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
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
        character = await self.config.guild(guild).characters.get_raw(name, default=None)
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
        await self.config.guild(guild).characters.clear_raw(name)
        embed = discord.Embed(
            title="🗑️ Character Deleted",
            description=f"The character **{name}** has been deleted.",
            color=0xFAA61A
        )
        embed.set_footer(text="Fable RP Tracker • Character Deleted", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="migrate", description="Migrate old character storage to per-object storage (admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def character_migrate(self, ctx: commands.Context):
        """
        Migrate old character storage to per-object storage. Only run once per server.
        """
        guild = ctx.guild
        characters = await self.config.guild(guild).characters()
        if not isinstance(characters, dict):
            await ctx.send("No migration needed or already migrated.")
            return
        migrated = 0
        for name, data in characters.items():
            await self.config.guild(guild).characters.set_raw(name, value=data)
            migrated += 1
        await self.config.guild(guild).characters.set({})
        await ctx.send(f"✅ Migrated {migrated} characters to per-object storage.")

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
        all_characters = await self.config.guild(guild).characters.get_attr("").get_raw()
        char_names = [c.strip() for c in characters.split(",") if c.strip()]
        involved = []
        missing = []
        for cname in char_names:
            char = await self.config.guild(guild).characters.get_raw(cname, default=None)
            if char:
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
        all_events = await self.config.guild(guild).events.get_attr("").get_raw()
        event_id = (max([int(eid) for eid in all_events] or [0]) + 1)
        event_data = {
            "id": event_id,
            "description": description,
            "ic_date": date or "Unspecified",
            "created_at": discord.utils.utcnow().isoformat(),
            "created_by": str(user.id),
            "characters": involved
        }
        await self.config.guild(guild).events.set_raw(str(event_id), value=event_data)
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

    @event.command(name="migrate", description="Migrate old event logs to per-object storage (admin only)")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def event_migrate(self, ctx: commands.Context):
        """
        Migrate old event logs to per-object storage. Only run once per server.
        """
        guild = ctx.guild
        logs = await self.config.guild(guild).logs()
        if not isinstance(logs, list):
            await ctx.send("No migration needed or already migrated.")
            return
        migrated = 0
        for event in logs:
            eid = str(event["id"])
            await self.config.guild(guild).events.set_raw(eid, value=event)
            migrated += 1
        await self.config.guild(guild).logs.set([])
        await ctx.send(f"✅ Migrated {migrated} events to per-object storage.")

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
        event = await self.config.guild(guild).events.get_raw(str(event_id), default=None)
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
        await self.config.guild(guild).events.set_raw(str(event_id), value=event)
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
        event = await self.config.guild(guild).events.get_raw(str(event_id), default=None)
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
        await self.config.guild(guild).events.clear_raw(str(event_id))
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
        all_events = await self.config.guild(guild).events.get_attr("").get_raw()
        events = []
        for eid in all_events:
            event = await self.config.guild(guild).events.get_raw(eid, default=None)
            if event:
                events.append(event)
        if not events:
            embed = discord.Embed(
                title="No Events Found",
                description="There are no events logged yet.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        number = number if number is not None else 5
        number = max(1, min(int(number), 20))
        events_sorted = sorted(events, key=lambda e: e.get("created_at", ""), reverse=True)
        selected = events_sorted[:number]
        embed = discord.Embed(
            title=f"Recent Events (Last {number})",
            color=0x7289DA
        )
        for event in selected:
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
        all_events = await self.config.guild(guild).events.get_attr("").get_raw()
        results = []
        for eid in all_events:
            event = await self.config.guild(guild).events.get_raw(eid, default=None)
            if event and keyword.lower() in event.get("description", "").lower():
                results.append(event)
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
        data = await self.config.guild(ctx.guild).all()
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
