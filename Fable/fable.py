from redbot.core import commands, Config
import discord
from typing import Optional, List

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
        }
        self.config.register_guild(**default_guild)

    @commands.hybrid_group(name="fable", description="A living world tracker for character-driven RP groups.")
    async def fable(self, ctx: commands.Context):
        """Parent command for Fable RP tracker."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # Character Profile System
    @commands.hybrid_group(name="character", description="Manage RP character profiles.")
    async def character(self, ctx: commands.Context):
        """Character profile management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="create", description="Create a new character profile with traits and relationships.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_create(self, ctx: commands.Context, name: str, *, args: str):
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
        embed.set_footer(text="Fable RP Tracker • Character Profile")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="edit", description="Edit a character's description, trait, or relationship.")
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
            embed.set_footer(text="Fable RP Tracker • Character Edit")
            await ctx.send(embed=embed)
        else:
            await ctx.send("No changes made (may already exist).")

    @commands.hybrid_command(name="view", description="View a character profile.")
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
        embed.set_footer(text="Fable RP Tracker • Character Profile")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="list", description="List all characters or those belonging to a user.")
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
            embed.set_footer(text="Fable RP Tracker • Character List")
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="delete", description="Delete a character profile.")
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
        embed.set_footer(text="Fable RP Tracker • Character Deleted")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="relations", description="Show all relationships for a character.")
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
        embed.set_footer(text="Fable RP Tracker • Character Relationships")
        await ctx.send(embed=embed)

    # Relationship Management
    @commands.hybrid_group(name="relationship", description="Manage character relationships.")
    async def relationship(self, ctx: commands.Context):
        """
        Relationship management commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="add", description="Add a relationship between two characters.")
    @commands.guild_only()
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
        # Optionally store relationship description in relationships config
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
        embed.set_footer(text="Fable RP Tracker • Relationship Added")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="edit", description="Edit a relationship's type or description.")
    @commands.guild_only()
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
        # Find the relationship key
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
            # Change the relationship type
            _, _, old_type = rel_key.split("|", 2)
            new_key = f"{character1}|{character2}|{new_value.lower()}"
            relationships[new_key] = relationships.pop(rel_key)
            # Update character1's relationships
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
            embed.set_footer(text="Fable RP Tracker • Relationship Edit")
            await ctx.send(embed=embed)
        elif field.lower() == "description":
            relationships[rel_key]["description"] = new_value
            await self.config.guild(guild).relationships.set(relationships)
            embed = discord.Embed(
                title="Relationship Description Updated",
                description=f"Description updated for **{character1}** and **{character2}**.",
                color=0x43B581
            )
            embed.set_footer(text="Fable RP Tracker • Relationship Edit")
            await ctx.send(embed=embed)
        else:
            await ctx.send("Unknown field. Use 'type' or 'description'.")

    @commands.hybrid_command(name="remove", description="Remove a relationship between two characters.")
    @commands.guild_only()
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
        # Remove from character1's relationships
        for rel_type, rel_list in char1["relationships"].items():
            if character2 in rel_list:
                rel_list.remove(character2)
                found = True
        # Remove from relationships config
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
            embed.set_footer(text="Fable RP Tracker • Relationship Removed")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Relationship Not Found",
                description=f"No relationship found between **{character1}** and **{character2}**.",
                color=0xF04747
            )
            await ctx.send(embed=embed)

    # Event Timeline
    @commands.hybrid_group(name="event", description="Log and manage in-character events.")
    async def event(self, ctx: commands.Context):
        """
        Event logging and management commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="log", description="Log an in-character event.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def event_log(self, ctx: commands.Context, *characters: str, description: str, date: Optional[str] = None):
        """
        Log an in-character event.
        
        Usage:
        [p]fable event log Vex Mira "Discovered the ancient tomb together" --date 3023-12-05
        """
        guild = ctx.guild
        user = ctx.author
        all_characters = await self.config.guild(guild).characters() or {}
        logs = await self.config.guild(guild).logs() or []
        involved = []
        missing = []
        for cname in characters:
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
        # Optionally increment relationship strength for shared events
        # (Not implemented here, but can be added)
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

    @commands.hybrid_command(name="edit", description="Edit an event's description.")
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
        embed.set_footer(text="Fable RP Tracker • Event Edit")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="delete", description="Delete an event.")
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
        embed.set_footer(text="Fable RP Tracker • Event Deleted")
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="timeline", description="View and search the event timeline.")
    async def timeline(self, ctx: commands.Context):
        """
        Timeline viewing and searching commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="recent", description="Show recent events.")
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
        embed.set_footer(text="Fable RP Tracker • Timeline")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="search", description="Search the timeline for a keyword.")
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
            embed.set_footer(text="Fable RP Tracker • Timeline Search")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="show", description="Show all events, optionally filtered by character or date range.")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def timeline_show(self, ctx: commands.Context, character: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None):
        """
        Show all events, optionally filtered by character or date range.
        
        Usage:
        [p]fable timeline show
        [p]fable timeline show Vex
        [p]fable timeline show Vex 3023-01-01 3023-12-31
        """
        guild = ctx.guild
        logs = await self.config.guild(guild).logs() or []
        filtered = logs
        if character:
            filtered = [e for e in filtered if character in e.get("characters", [])]
        if from_date:
            filtered = [e for e in filtered if e.get("ic_date") and e["ic_date"] >= from_date]
        if to_date:
            filtered = [e for e in filtered if e.get("ic_date") and e["ic_date"] <= to_date]
        if not filtered:
            embed = discord.Embed(
                title="No Events Found",
                description="No events found for the given filters.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        # Paginate if more than 10 events
        pages = [filtered[i:i+10] for i in range(0, len(filtered), 10)]
        for idx, page in enumerate(pages, 1):
            embed = discord.Embed(
                title=f"Timeline Events (Page {idx}/{len(pages)})",
                color=0x7289DA
            )
            for event in page:
                chars = ", ".join(event.get("characters", []))
                desc = event.get("description", "No description.")
                ic_date = event.get("ic_date", "Unspecified")
                eid = event.get("id", "?")
                embed.add_field(
                    name=f"Event {eid} | {ic_date}",
                    value=f"**Characters:** {chars}\n{desc}",
                    inline=False
                )
            embed.set_footer(text="Fable RP Tracker • Timeline Show")
            await ctx.send(embed=embed)

    # Collaborative Lore System
    @commands.hybrid_group(name="lore", description="Collaborative worldbuilding commands.")
    async def lore(self, ctx: commands.Context):
        """
        Lore collaboration commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="suggest", description="Suggest a new lore entry.")
    async def lore_suggest(self, ctx: commands.Context, name: str, description: str, type: Optional[str] = None):
        """
        Suggest a new lore entry.
        """
        await ctx.send("Lore suggest not yet implemented.")

    @commands.hybrid_command(name="approve", description="Approve a suggested lore entry.")
    async def lore_approve(self, ctx: commands.Context, lore_id: int):
        """
        Approve a suggested lore entry.
        """
        await ctx.send("Lore approve not yet implemented.")

    @commands.hybrid_command(name="deny", description="Deny a suggested lore entry.")
    async def lore_deny(self, ctx: commands.Context, lore_id: int):
        """
        Deny a suggested lore entry.
        """
        await ctx.send("Lore deny not yet implemented.")

    @commands.hybrid_command(name="edit", description="Edit a lore entry's description.")
    async def lore_edit(self, ctx: commands.Context, name: str, new_description: str):
        """
        Edit a lore entry's description.
        """
        await ctx.send("Lore edit not yet implemented.")

    @commands.hybrid_command(name="view", description="View a lore entry.")
    async def lore_view(self, ctx: commands.Context, name: str):
        """
        View a lore entry.
        """
        await ctx.send("Lore view not yet implemented.")

    @commands.hybrid_command(name="list", description="List all lore entries, optionally filtered by type.")
    async def lore_list(self, ctx: commands.Context, type: Optional[str] = None):
        """
        List all lore entries, optionally filtered by type.
        """
        await ctx.send("Lore list not yet implemented.")

    @commands.hybrid_command(name="search", description="Search lore entries by keyword.")
    async def lore_search(self, ctx: commands.Context, keyword: str):
        """
        Search lore entries by keyword.
        """
        await ctx.send("Lore search not yet implemented.")

    # IC Mail System
    @commands.hybrid_group(name="mail", description="In-character mail system.")
    async def mail(self, ctx: commands.Context):
        """
        In-character mail system commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="send", description="Send IC mail to a recipient.")
    async def mail_send(self, ctx: commands.Context, recipient: str, message: str, from_character: Optional[str] = None):
        """
        Send IC mail to a recipient.
        """
        await ctx.send("Mail send not yet implemented.")

    @commands.hybrid_command(name="read", description="Read IC mail (all or unread).")
    async def mail_read(self, ctx: commands.Context, filter: Optional[str] = "unread"):
        """
        Read IC mail (all or unread).
        """
        await ctx.send("Mail read not yet implemented.")

    @commands.hybrid_command(name="view", description="View a specific mail message.")
    async def mail_view(self, ctx: commands.Context, mail_id: int):
        """
        View a specific mail message.
        """
        await ctx.send("Mail view not yet implemented.")

    @commands.hybrid_command(name="delete", description="Delete a mail message.")
    async def mail_delete(self, ctx: commands.Context, mail_id: int):
        """
        Delete a mail message.
        """
        await ctx.send("Mail delete not yet implemented.")

    # Google Docs Sync
    @commands.hybrid_group(name="sync", description="Google Sheets sync commands.")
    async def sync(self, ctx: commands.Context):
        """
        Google Sheets sync commands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @commands.hybrid_command(name="setup", description="Set up Google Sheets sync.")
    async def sync_setup(self, ctx: commands.Context, google_sheet_url: str, api_key: str):
        """
        Set up Google Sheets sync.
        """
        await ctx.send("Sync setup not yet implemented.")

    @commands.hybrid_command(name="export", description="Export data to Google Sheets.")
    async def sync_export(self, ctx: commands.Context, data_type: Optional[str] = None):
        """
        Export data to Google Sheets.
        """
        await ctx.send("Sync export not yet implemented.")

    @commands.hybrid_command(name="import", description="Import data from Google Sheets.")
    async def sync_import(self, ctx: commands.Context, data_type: Optional[str] = None):
        """
        Import data from Google Sheets.
        """
        await ctx.send("Sync import not yet implemented.")

    @commands.hybrid_command(name="status", description="Show Google Sheets sync status.")
    async def sync_status(self, ctx: commands.Context):
        """
        Show Google Sheets sync status.
        """
        await ctx.send("Sync status not yet implemented.")

    # Administrative Commands
    @fable.hybrid_command(name="setup", description="Run the Fable setup wizard.")
    async def setup_cmd(self, ctx: commands.Context):
        """
        Run the Fable setup wizard.
        """
        await ctx.send("Setup wizard not yet implemented.")

    @fable.hybrid_command(name="settings", description="View or edit Fable settings.")
    async def settings(self, ctx: commands.Context):
        """
        View or edit Fable settings.
        """
        await ctx.send("Settings not yet implemented.")

    @fable.hybrid_command(name="backup", description="Create a backup of Fable data.")
    async def backup(self, ctx: commands.Context):
        """
        Create a backup of Fable data.
        """
        await ctx.send("Backup not yet implemented.")

    @fable.hybrid_command(name="restore", description="Restore Fable data from a backup file.")
    async def restore(self, ctx: commands.Context, backup_file: str):
        """
        Restore Fable data from a backup file.
        """
        await ctx.send("Restore not yet implemented.")

    @fable.hybrid_command(name="permissions", description="Set Fable permissions for a role.")
    async def permissions(self, ctx: commands.Context, role: discord.Role, permission_level: str):
        """
        Set Fable permissions for a role.
        """
        await ctx.send("Permissions not yet implemented.")

    async def cog_unload(self):
        """Cleanup tasks when the cog is unloaded."""
        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Fable(bot))
