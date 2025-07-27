from redbot.core import commands, Config
import discord
from typing import Optional, List
import aiohttp
from Fable.google_sync_utils import (
    export_to_sheet, import_to_sheet, export_to_doc, import_from_doc
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
            "locations": {},  # New locations system
            "story_arcs": {},  # New story arcs system
            "milestones": {},  # Character development milestones
            "relationship_history": {},  # Enhanced relationship tracking
            "mail": {},
            "sync": {},
            "settings": {
                "relationship_intensity_levels": [
                    "Stranger",
                    "Acquaintance",
                    "Friend",
                    "Close Friend",
                    "Best Friend/Rival/Love Interest"
                ],
                "milestone_categories": [
                    "Personal Growth",
                    "Relationship Development",
                    "Story Progress",
                    "Achievement",
                    "Character Development"
                ]
            },
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

    # Development Tracking System
    @fable.group(name="milestone", description="Track character development and milestones.")
    @commands.guild_only()
    async def milestone(self, ctx: commands.Context):
        """Character development milestone tracking commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # Location System
    @fable.group(name="location", description="Manage RP locations and scenes.")
    @commands.guild_only()
    async def location(self, ctx: commands.Context):
        """Location and scene management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
            
    # Story Arc System
    @fable.group(name="arc", description="Manage character story arcs and plot progression.")
    @commands.guild_only()
    async def arc(self, ctx: commands.Context):
        """Story arc and plot progression commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

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
        identity_fields = [
            ("name", "The character's short name (required)"),
            ("full_name", "Full legal or known name (optional)"),
            ("species", "The character's species/race (optional)"),
            ("gender", "Gender identity (optional)"),
            ("date_of_birth", "Date of birth (optional)"),
            ("age", "The character's age (optional)"),
            ("age_appearance", "Apparent age (optional)"),
            ("true_age", "True age (optional)")
        ]
        
        basic_fields = [
            ("ethnicity", "Ethnic background (optional)"),
            ("occupation", "The character's job or role (optional)"),
            ("height", "Height (optional)"),
            ("weight", "Weight (optional)"),
            ("sexual_orientation", "Sexual orientation (optional)"),
            ("zodiac", "Zodiac sign (optional)"),
            ("alignment", "Moral alignment (optional)")
        ]
        
        personality_fields = [
            ("description", "A detailed description (required)"),
            ("image_url", "URL to character's image/avatar (optional)"),
            ("traits", "One or more personality traits (optional, use --trait)"),
            ("background", "Character's history and backstory (optional)"),
            ("goals", "Character's current goals and aspirations (optional, use --goal)"),
            ("languages", "Languages the character knows (optional, use --language)"),
            ("quote", "Memorable quote or catchphrase (optional)"),
            ("inventory", "Notable items or equipment (optional, use --item)")
        ]
        
        relationship_fields = [
            ("relationships", "Allies, rivals, and neutrals (optional, use --ally, --rival, --neutral)"),
            ("family", "Family ties and connections (optional, use --family)")
        ]

        embed = discord.Embed(
            title="Available Character Fields",
            description="Use these fields when creating or editing characters.",
            color=0x7289DA
        )

        # Create field groups in embed
        embed.add_field(
            name="📝 Identity",
            value="\n".join(f"`{fname}` - {fdesc}" for fname, fdesc in identity_fields),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Basic Information",
            value="\n".join(f"`{fname}` - {fdesc}" for fname, fdesc in basic_fields),
            inline=False
        )
        
        embed.add_field(
            name="🎭 Personality & Background",
            value="\n".join(f"`{fname}` - {fdesc}" for fname, fdesc in personality_fields),
            inline=False
        )
        
        embed.add_field(
            name="👥 Relationships",
            value="\n".join(f"`{fname}` - {fdesc}" for fname, fdesc in relationship_fields),
            inline=False
        )
        
        embed.set_footer(text="Fable RP Tracker • Character Fields", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="create", description="Create a new character profile with all fields.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def create(self, ctx: commands.Context,
        name: str = commands.parameter(description="Short name for the character."),
        description: str = commands.parameter(description="A detailed description."),
        image_url: Optional[str] = commands.parameter(default=None, description="URL to character's image/avatar."),
        background: Optional[str] = commands.parameter(default=None, description="Character's history and backstory."),
        quote: Optional[str] = commands.parameter(default=None, description="Memorable quote or catchphrase."),
        full_name: Optional[str] = commands.parameter(default=None, description="Full legal or known name."),
        species: Optional[str] = commands.parameter(default=None, description="Species or race."),
        gender: Optional[str] = commands.parameter(default=None, description="Gender identity."),
        date_of_birth: Optional[str] = commands.parameter(default=None, description="Date of birth."),
        age_appearance: Optional[str] = commands.parameter(default=None, description="Apparent age."),
        true_age: Optional[str] = commands.parameter(default=None, description="True age."),
        ethnicity: Optional[str] = commands.parameter(default=None, description="Ethnic background."),
        occupation: Optional[str] = commands.parameter(default=None, description="Job or role."),
        height: Optional[str] = commands.parameter(default=None, description="Height."),
        weight: Optional[str] = commands.parameter(default=None, description="Weight."),
        sexual_orientation: Optional[str] = commands.parameter(default=None, description="Sexual orientation."),
        zodiac: Optional[str] = commands.parameter(default=None, description="Zodiac sign."),
        alignment: Optional[str] = commands.parameter(default=None, description="Moral alignment."),
        traits: Optional[str] = commands.parameter(default=None, description="Comma-separated list of traits."),
        goals: Optional[str] = commands.parameter(default=None, description="Comma-separated list of goals."),
        languages: Optional[str] = commands.parameter(default=None, description="Comma-separated list of languages."),
        inventory: Optional[str] = commands.parameter(default=None, description="Comma-separated list of items."),
        family: Optional[str] = commands.parameter(default=None, description="Comma-separated list of family members."),
        allies: Optional[str] = commands.parameter(default=None, description="Comma-separated list of allies."),
        rivals: Optional[str] = commands.parameter(default=None, description="Comma-separated list of rivals."),
        neutrals: Optional[str] = commands.parameter(default=None, description="Comma-separated list of neutrals.")
    ):
        """Create a new character profile with all available fields."""
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

        # Validate image URL if provided
        if image_url:
            try:
                embed = discord.Embed()
                embed.set_thumbnail(url=image_url)
                await ctx.send(embed=embed, delete_after=1)
            except discord.errors.InvalidArgument:
                await ctx.send("❌ Invalid image URL. Please provide a direct link to an image file.")
                return
            except Exception:
                await ctx.send("❌ Could not validate image URL. Please check the URL and try again.")
                return

        # Parse comma-separated fields
        traits_list = [t.strip() for t in traits.split(",") if t.strip()] if traits else []
        goals_list = [g.strip() for g in goals.split(",") if g.strip()] if goals else []
        languages_list = [l.strip() for l in languages.split(",") if l.strip()] if languages else []
        inventory_list = [i.strip() for i in inventory.split(",") if i.strip()] if inventory else []
        family_list = [f.strip() for f in family.split(",") if f.strip()] if family else []
        allies_list = [a.strip() for a in allies.split(",") if a.strip()] if allies else []
        rivals_list = [r.strip() for r in rivals.split(",") if r.strip()] if rivals else []
        neutrals_list = [n.strip() for n in neutrals.split(",") if n.strip()] if neutrals else []
        
        character_data = {
            "name": name,
            "full_name": full_name,
            "description": description,
            "background": background,
            "quote": quote,
            "image_url": image_url,
            "owner_id": user_id,
            "species": species,
            "gender": gender,
            "date_of_birth": date_of_birth,
            "age_appearance": age_appearance,
            "true_age": true_age,
            "ethnicity": ethnicity,
            "occupation": occupation,
            "height": height,
            "weight": weight,
            "sexual_orientation": sexual_orientation,
            "zodiac": zodiac,
            "alignment": alignment,
            "traits": traits_list,
            "goals": goals_list,
            "languages": languages_list,
            "inventory": inventory_list,
            "family": family_list,
            "relationships": {
                "ally": allies_list,
                "rival": rivals_list,
                "neutral": neutrals_list,
                "family": family_list
            }
        }
        
        await self.config.guild(guild).characters.set_raw(name, value=character_data)
        
        # Create embed with sections
        embed = discord.Embed(
            title=f"Character Created: {name}",
            color=0x43B581
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        if image_url:
            embed.set_thumbnail(url=image_url)

        # Identity Section
        identity = []
        if full_name:
            identity.append(f"**Full Name:** {full_name}")
        if species:
            identity.append(f"**Species:** {species}")
        if gender:
            identity.append(f"**Gender:** {gender}")
        if date_of_birth:
            identity.append(f"**Date of Birth:** {date_of_birth}")
        if age_appearance:
            identity.append(f"**Age Appearance:** {age_appearance}")
        if true_age:
            identity.append(f"**True Age:** {true_age}")
        if identity:
            embed.add_field(name="📝 Identity", value="\n".join(identity), inline=False)

        # Basic Info Section
        basics = []
        if ethnicity:
            basics.append(f"**Ethnicity:** {ethnicity}")
        if occupation:
            basics.append(f"**Occupation:** {occupation}")
        if height:
            basics.append(f"**Height:** {height}")
        if weight:
            basics.append(f"**Weight:** {weight}")
        if sexual_orientation:
            basics.append(f"**Sexual Orientation:** {sexual_orientation}")
        if zodiac:
            basics.append(f"**Zodiac:** {zodiac}")
        if alignment:
            basics.append(f"**Alignment:** {alignment}")
        if basics:
            embed.add_field(name="ℹ️ Basic Information", value="\n".join(basics), inline=False)

        # Description & Background
        if description:
            embed.add_field(name="📖 Description", value=description[:1024], inline=False)
        if background:
            embed.add_field(name="📜 Background", value=background[:1024], inline=False)
        if quote:
            embed.add_field(name="💭 Quote", value=quote, inline=False)

        # Lists Section
        if traits_list:
            embed.add_field(name="🎭 Traits", value="\n".join(f"• {t}" for t in traits_list), inline=False)
        if goals_list:
            embed.add_field(name="🎯 Goals", value="\n".join(f"• {g}" for g in goals_list), inline=False)
        if languages_list:
            embed.add_field(name="🗣️ Languages", value="\n".join(f"• {l}" for l in languages_list), inline=False)
        if inventory_list:
            embed.add_field(name="🎒 Inventory", value="\n".join(f"• {i}" for i in inventory_list), inline=False)

        # Relationships Section
        relationships = []
        if family_list:
            relationships.append("**Family:**\n" + "\n".join(f"• {f}" for f in family_list))
        if allies_list:
            relationships.append("**Allies:**\n" + "\n".join(f"• {a}" for a in allies_list))
        if rivals_list:
            relationships.append("**Rivals:**\n" + "\n".join(f"• {r}" for r in rivals_list))
        if neutrals_list:
            relationships.append("**Neutral:**\n" + "\n".join(f"• {n}" for n in neutrals_list))
        if relationships:
            embed.add_field(name="👥 Relationships", value="\n\n".join(relationships), inline=False)

        embed.set_footer(text="Fable RP Tracker • Character Creation", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="edit", description="Edit a character field.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_edit(self, ctx: commands.Context, name: str, field: str, *, new_value: str):
        """
        Edit a character's field.
        Usage:
        [p]fable character edit "Athena" background "New background story..."
        [p]fable character edit "Athena" goals "Become a master mage, Find the lost artifacts"
        [p]fable character edit "Athena" languages "Common, Elvish, Draconic"
        [p]fable character edit "Athena" quote "Magic is just science we don't understand yet."
        [p]fable character edit "Athena" inventory "Spellbook, Staff of Power, Enchanted Robes"
        [p]fable character edit "Athena" family "Sister: Artemis, Mother: Hera"
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

        # Handle list-type fields
        list_fields = {
            "traits": "traits",
            "goals": "goals",
            "languages": "languages",
            "inventory": "inventory",
            "family": "family"
        }

        if field in list_fields:
            field_name = list_fields[field]
            if field_name not in character:
                character[field_name] = []
            new_items = [item.strip() for item in new_value.split(",") if item.strip()]
            character[field_name] = new_items
            updated = True

        # Handle relationship fields
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

        # Handle image URL
        elif field == "image_url":
            try:
                embed = discord.Embed()
                embed.set_thumbnail(url=new_value)
                await ctx.send(embed=embed, delete_after=1)
                character["image_url"] = new_value
                updated = True
            except discord.errors.InvalidArgument:
                await ctx.send("❌ Invalid image URL. Please provide a direct link to an image file.")
                return
            except Exception:
                await ctx.send("❌ Could not validate image URL. Please check the URL and try again.")
                return

        # Handle all other fields
        elif field in ("full_name", "species", "gender", "date_of_birth", "age", "age_appearance", 
                      "true_age", "ethnicity", "occupation", "height", "weight", "sexual_orientation", 
                      "zodiac", "alignment", "description", "background", "quote"):
            character[field] = new_value
            updated = True
        else:
            await ctx.send("Unknown field. Use the fields command to see all options.")
            return

        if updated:
            await self.config.guild(guild).characters.set_raw(name, value=character)
            embed = discord.Embed(
                title="✅ Character Updated",
                description=f"**{name}**'s {field.replace('_', ' ')} updated.",
                color=0x43B581
            )
            
            # Show the new value in the embed
            if field in list_fields:
                new_list = character[list_fields[field]]
                if new_list:
                    embed.add_field(
                        name=f"New {field.capitalize()}", 
                        value="\n".join(f"• {item}" for item in new_list),
                        inline=False
                    )
            elif field != "image_url":  # Image URL is shown via thumbnail
                embed.add_field(name=f"New {field.replace('_', ' ').capitalize()}", value=new_value, inline=False)
            
            if field == "image_url" and new_value:
                embed.set_thumbnail(url=new_value)
                
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
        [p]fable character view "Athena"
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
        
        # Create initial embed
        embed = discord.Embed(
            title=f"{character['name']}",
            color=0x7289DA
        )
        if owner:
            embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        if character.get("image_url"):
            embed.set_thumbnail(url=character["image_url"])
        if character.get("quote"):
            embed.description = f"*\"{character['quote']}\"*"

        # Identity Section
        identity = []
        if character.get("full_name"):
            identity.append(f"**Full Name:** {character['full_name']}")
        if character.get("species"):
            identity.append(f"**Species:** {character['species']}")
        if character.get("gender"):
            identity.append(f"**Gender:** {character['gender']}")
        if character.get("date_of_birth"):
            identity.append(f"**Date of Birth:** {character['date_of_birth']}")
        if character.get("age_appearance"):
            identity.append(f"**Age Appearance:** {character['age_appearance']}")
        if character.get("true_age"):
            identity.append(f"**True Age:** {character['true_age']}")
        if identity:
            embed.add_field(name="📝 Identity", value="\n".join(identity), inline=False)

        # Basic Info Section
        basics = []
        if character.get("ethnicity"):
            basics.append(f"**Ethnicity:** {character['ethnicity']}")
        if character.get("occupation"):
            basics.append(f"**Occupation:** {character['occupation']}")
        if character.get("height"):
            basics.append(f"**Height:** {character['height']}")
        if character.get("weight"):
            basics.append(f"**Weight:** {character['weight']}")
        if character.get("sexual_orientation"):
            basics.append(f"**Sexual Orientation:** {character['sexual_orientation']}")
        if character.get("zodiac"):
            basics.append(f"**Zodiac:** {character['zodiac']}")
        if character.get("alignment"):
            basics.append(f"**Alignment:** {character['alignment']}")
        if basics:
            embed.add_field(name="ℹ️ Basic Information", value="\n".join(basics), inline=False)

        # Description & Background
        if character.get("description"):
            description = character["description"]
            if len(description) > 1024:
                embed.add_field(name="📖 Description", value=f"{description[:1021]}...", inline=False)
            else:
                embed.add_field(name="📖 Description", value=description, inline=False)

        if character.get("background"):
            background = character["background"]
            if len(background) > 1024:
                embed.add_field(name="📜 Background", value=f"{background[:1021]}...", inline=False)
            else:
                embed.add_field(name="📜 Background", value=background, inline=False)

        # Character Details
        if character.get("traits"):
            embed.add_field(name="🎭 Traits", value="\n".join(f"• {t}" for t in character["traits"]), inline=False)
        if character.get("goals"):
            embed.add_field(name="🎯 Goals", value="\n".join(f"• {g}" for g in character["goals"]), inline=False)
        if character.get("languages"):
            embed.add_field(name="🗣️ Languages", value="\n".join(f"• {l}" for l in character["languages"]), inline=False)
        if character.get("inventory"):
            embed.add_field(name="🎒 Inventory", value="\n".join(f"• {i}" for i in character["inventory"]), inline=False)

        # Relationships Section
        relationships = []
        if character.get("family"):
            relationships.append("**Family:**\n" + "\n".join(f"• {f}" for f in character["family"]))
        for rel_type, rel_list in character.get("relationships", {}).items():
            if rel_list and rel_type != "family":  # Family is handled separately
                relationships.append(f"**{rel_type.capitalize()}s:**\n" + "\n".join(f"• {r}" for r in rel_list))
        if relationships:
            embed.add_field(name="👥 Relationships", value="\n\n".join(relationships), inline=False)

        embed.set_footer(text="Fable RP Tracker • Character Profile", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

        # If description or background is too long, send as a file
        long_texts = []
        if character.get("description", "") and len(character["description"]) > 1024:
            long_texts.append(("Description", character["description"]))
        if character.get("background", "") and len(character["background"]) > 1024:
            long_texts.append(("Background", character["background"]))
        
        if long_texts:
            import io
            for title, content in long_texts:
                file = discord.File(
                    fp=io.BytesIO(content.encode("utf-8")), 
                    filename=f"{name}_{title.lower()}.txt"
                )
                await ctx.send(content=f"Full {title} for **{name}** (continued):", file=file)

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
        [p]fable character delete "Athena"
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
        [p]fable relations "Athena"
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
    @fable.group(name="relationship", description="Manage character relationships and connections.")
    @commands.guild_only()
    async def relationship(self, ctx: commands.Context):
        """Enhanced relationship management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @relationship.command(name="set", description="Set or update a relationship between characters.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relationship_set(
        self, 
        ctx: commands.Context,
        character1: str,
        character2: str,
        relationship_type: str,
        intensity: Optional[int] = 3,
        *,
        description: Optional[str] = None
    ):
        """
        Set or update a relationship between two characters.

        Parameters
        ----------
        character1: str
            First character's name
        character2: str
            Second character's name
        relationship_type: str
            Type of relationship (ally/rival/neutral/family)
        intensity: Optional[int]
            Relationship intensity (1-5, default: 3)
        description: Optional[str]
            Description of the relationship
        """
        guild = ctx.guild
        user = ctx.author
        characters = await self.config.guild(guild).characters()
        char1 = characters.get(character1)
        char2 = characters.get(character2)
        
        if not char1 or not char2:
            await ctx.send("❌ Both characters must exist to set a relationship.")
            return

        if not (str(user.id) == char1["owner_id"] or ctx.author.guild_permissions.administrator):
            await ctx.send("❌ Only the owner of the first character or an admin can set relationships.")
            return

        settings = await self.config.guild(guild).settings()
        intensity_levels = settings.get("relationship_intensity_levels", [])
        
        if not 1 <= intensity <= 5:
            await ctx.send("❌ Intensity must be between 1 and 5.")
            return

        relationship_data = {
            "type": relationship_type.lower(),
            "intensity": intensity,
            "intensity_label": intensity_levels[intensity - 1] if intensity_levels else str(intensity),
            "description": description,
            "updated_at": discord.utils.utcnow().isoformat(),
            "updated_by": str(user.id)
        }

        # Update relationship history
        history = await self.config.guild(guild).relationship_history()
        rel_key = f"{character1}|{character2}"
        if rel_key not in history:
            history[rel_key] = []
        
        # Add to history before updating current relationship
        if rel_key in characters.get(character1, {}).get("relationships", {}):
            old_rel = characters[character1]["relationships"][rel_key]
            history[rel_key].append({
                "type": old_rel.get("type", "unknown"),
                "intensity": old_rel.get("intensity", 1),
                "description": old_rel.get("description", ""),
                "start_date": old_rel.get("updated_at", ""),
                "end_date": discord.utils.utcnow().isoformat()
            })

        # Update current relationships
        if "relationships" not in char1:
            char1["relationships"] = {}
        char1["relationships"][rel_key] = relationship_data
        characters[character1] = char1
        
        await self.config.guild(guild).characters.set(characters)
        await self.config.guild(guild).relationship_history.set(history)

        embed = discord.Embed(
            title="👥 Relationship Updated",
            description=f"Relationship between **{character1}** and **{character2}** has been updated.",
            color=0x43B581
        )
        embed.add_field(
            name="Details", 
            value=f"**Type:** {relationship_type.title()}\n"
                  f"**Intensity:** {intensity}/5 ({relationship_data['intensity_label']})"
                  + (f"\n**Description:** {description}" if description else ""),
            inline=False
        )
        embed.set_footer(text="Fable RP Tracker • Relationships")
        await ctx.send(embed=embed)

    @relationship.command(name="view", description="View relationship details and history.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def relationship_view(
        self,
        ctx: commands.Context,
        character1: str,
        character2: str
    ):
        """
        View the relationship between two characters.

        Parameters
        ----------
        character1: str
            First character's name
        character2: str
            Second character's name
        """
        guild = ctx.guild
        characters = await self.config.guild(guild).characters()
        char1 = characters.get(character1)
        
        if not char1:
            await ctx.send(f"❌ Character '{character1}' not found.")
            return

        rel_key = f"{character1}|{character2}"
        current_rel = char1.get("relationships", {}).get(rel_key)
        
        if not current_rel:
            await ctx.send(f"No relationship found between {character1} and {character2}.")
            return

        embed = discord.Embed(
            title=f"👥 Relationship: {character1} & {character2}",
            color=0x7289DA
        )
        
        # Current relationship
        embed.add_field(
            name="Current Relationship",
            value=f"**Type:** {current_rel['type'].title()}\n"
                  f"**Intensity:** {current_rel['intensity']}/5 ({current_rel['intensity_label']})\n"
                  + (f"**Description:** {current_rel['description']}" if current_rel.get('description') else ""),
            inline=False
        )

        # Relationship history
        history = await self.config.guild(guild).relationship_history()
        if rel_key in history and history[rel_key]:
            history_text = ""
            for past_rel in reversed(history[rel_key][-3:]):  # Show last 3 changes
                start_date = discord.utils.parse_time(past_rel['start_date'])
                end_date = discord.utils.parse_time(past_rel['end_date'])
                history_text += f"**{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}**\n"
                history_text += f"Type: {past_rel['type'].title()}, Intensity: {past_rel['intensity']}/5\n"
                if past_rel.get('description'):
                    history_text += f"Note: {past_rel['description']}\n"
                history_text += "\n"
            
            if history_text:
                embed.add_field(name="📜 Relationship History", value=history_text.strip(), inline=False)

        embed.set_footer(text="Fable RP Tracker • Relationship Details")
        await ctx.send(embed=embed)

    @relationship.command(name="graph", description="Generate a visual relationship graph.")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def relationship_graph(
        self,
        ctx: commands.Context,
        character: Optional[str] = None
    ):
        """
        Generate a visual graph of character relationships.

        Parameters
        ----------
        character: Optional[str]
            Focus on a specific character's relationships
        """
        # Note: This is a placeholder for the relationship visualization feature
        # In the future, we can generate actual graphs using tools like graphviz
        await ctx.send("🚧 Relationship visualization feature coming soon!")

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
        [p]fable event log "Athena, Mira" "Discovered the ancient tomb together" --date 3023-12-05
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

    @fable.group(name="visualize", description="Create visual representations of data.")
    @commands.guild_only()
    async def visualize(self, ctx: commands.Context):
        """Commands for creating visual representations of relationships and locations."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @visualize.command(name="relationships", description="Generate a relationship graph.")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def visualize_relationships(
        self,
        ctx: commands.Context,
        character: Optional[str] = None
    ):
        """
        Generate a visual graph of character relationships.

        Parameters
        ----------
        character: Optional[str]
            Focus on a specific character's relationships
        """
        try:
            import graphviz
        except ImportError:
            await ctx.send("📦 Installing required package (graphviz)...")
            try:
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "graphviz"])
                import graphviz
            except Exception as e:
                await ctx.send(f"❌ Failed to install required package: {e}")
                return

        from .visualization_utils import create_relationship_graph
        
        guild = ctx.guild
        characters = await self.config.guild(guild).characters()
        
        # Filter relationships based on character if specified
        if character:
            if character not in characters:
                await ctx.send(f"❌ Character '{character}' not found.")
                return
            rel_data = {character: characters[character].get("relationships", {})}
        else:
            rel_data = {name: char.get("relationships", {}) 
                       for name, char in characters.items()}

        # Generate DOT graph
        dot_string = create_relationship_graph(rel_data)
        
        # Create and save the graph
        dot = graphviz.Source(dot_string)
        filename = f"relationships_{guild.id}"
        try:
            dot.render(filename, format="png", cleanup=True)
            await ctx.send(
                content="👥 Character Relationship Graph:",
                file=discord.File(f"{filename}.png")
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to generate graph: {e}")
        finally:
            try:
                import os
                if os.path.exists(f"{filename}.png"):
                    os.remove(f"{filename}.png")
            except:
                pass

    @visualize.command(name="locations", description="Generate a location map.")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def visualize_locations(self, ctx: commands.Context):
        """Generate a visual map of connected locations."""
        try:
            import graphviz
        except ImportError:
            await ctx.send("📦 Installing required package (graphviz)...")
            try:
                import subprocess
                subprocess.run([sys.executable, "-m", "pip", "install", "graphviz"])
                import graphviz
            except Exception as e:
                await ctx.send(f"❌ Failed to install required package: {e}")
                return

        from .visualization_utils import create_location_map
        
        guild = ctx.guild
        locations = await self.config.guild(guild).locations()
        
        if not locations:
            await ctx.send("No locations found.")
            return

        # Generate DOT graph
        dot_string = create_location_map(locations)
        
        # Create and save the graph
        dot = graphviz.Source(dot_string)
        filename = f"locations_{guild.id}"
        try:
            dot.render(filename, format="png", cleanup=True)
            await ctx.send(
                content="🗺️ Location Map:",
                file=discord.File(f"{filename}.png")
            )
        except Exception as e:
            await ctx.send(f"❌ Failed to generate map: {e}")
        finally:
            try:
                import os
                if os.path.exists(f"{filename}.png"):
                    os.remove(f"{filename}.png")
            except:
                pass

    @character.group(name="timeline", description="View a character's visual timeline.")
    @commands.guild_only()
    async def character_timeline(self, ctx: commands.Context):
        """View a character's development timeline with visual elements."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @character_timeline.command(name="view", description="View a character's timeline.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def timeline_view(
        self,
        ctx: commands.Context,
        character: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_type: Optional[str] = None
    ):
        """
        View a character's timeline with optional filters.

        Parameters
        ----------
        character: str
            The character's name
        start_date: Optional[str]
            Filter events after this date (YYYY-MM-DD)
        end_date: Optional[str]
            Filter events before this date (YYYY-MM-DD)
        event_type: Optional[str]
            Filter by event type (milestone/relationship/story/etc)
        """
        from .visualization_utils import create_timeline_embed

        guild = ctx.guild
        events = []

        # Collect milestone events
        milestones = await self.config.guild(guild).milestones()
        char_milestones = milestones.get(character, [])
        for milestone in char_milestones:
            events.append({
                "type": "Milestone",
                "title": milestone["title"],
                "description": milestone["description"],
                "date": milestone["date"]
            })

        # Collect relationship events
        history = await self.config.guild(guild).relationship_history()
        for rel_key, rel_history in history.items():
            if character in rel_key:
                for rel in rel_history:
                    events.append({
                        "type": "Relationship",
                        "title": f"Relationship Change ({rel['type']})",
                        "description": rel.get('description', ''),
                        "date": rel["start_date"]
                    })

        # Collect story arc events
        story_arcs = await self.config.guild(guild).story_arcs()
        char_arcs = story_arcs.get(character, [])
        for arc in char_arcs:
            events.append({
                "type": "Story",
                "title": arc["title"],
                "description": arc["description"],
                "date": arc["created_at"]
            })

        # Collect location visits
        locations = await self.config.guild(guild).locations()
        for loc_name, loc_data in locations.items():
            for visit in loc_data.get("visits", []):
                if visit["character"] == character:
                    events.append({
                        "type": "Location",
                        "title": f"Visited {loc_name}",
                        "description": visit.get("note", ""),
                        "date": visit["timestamp"]
                    })

        embed = create_timeline_embed(
            events=events,
            char_name=character,
            start_date=start_date,
            end_date=end_date,
            event_type=event_type
        )
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
            msg = "❌ No Google API key is set for this server."
            color = 0xF04747
        embed = discord.Embed(
            title="Google API Key Status",
            description=msg,
            color=color
        )
        embed.set_footer(text="Fable RP Tracker • Google API", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="template", description="Show a character template for a specific genre.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_template(self, ctx: commands.Context, genre: str = "fantasy"):
        """
        Get a character template for a specific genre to help with character creation.
        
        Usage:
        [p]fable character template fantasy
        [p]fable character template modern
        [p]fable character template scifi
        [p]fable character template supernatural
        """
        from .character_templates import get_template
        
        template = get_template(genre)
        
        embed = discord.Embed(
            title=f"{genre.capitalize()} Character Template",
            description=template["description"],
            color=0x7289DA
        )
        
        for field, value in template["fields"].items():
            if isinstance(value, list):
                embed.add_field(
                    name=field.replace("_", " ").capitalize(),
                    value="\n".join(f"• {item}" for item in value),
                    inline=False
                )
            else:
                embed.add_field(
                    name=field.replace("_", " ").capitalize(),
                    value=value,
                    inline=True
                )
        
        example_command = (
            f"--[p]fable character create \"Character Name\" \"A detailed description\" "
            f"--species \"{template['fields'].get('species', 'Species')}\" "
            f"--traits \"{', '.join(template['fields'].get('traits', []))}\" "
            f"--languages \"{', '.join(template['fields'].get('languages', []))}\" "
            f"--inventory \"{', '.join(template['fields'].get('inventory', []))}\" "
            f"--goals \"{', '.join(template['fields'].get('goals', []))}\""
        )
        
        embed.add_field(
            name="Example Command",
            value=f"{example_command}",
            inline=False
        )
        
        embed.set_footer(text="Fable RP Tracker • Character Template", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @character.command(name="quickstart", description="Quickly create a character using a template.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def character_quickstart(self, ctx: commands.Context, name: str, genre: str = "fantasy"):
        """
        Quickly create a character using a genre template as a starting point.
        
        Usage:
        [p]fable character quickstart "Athena" fantasy
        [p]fable character quickstart "John Smith" modern
        [p]fable character quickstart "Commander Zero" scifi
        [p]fable character quickstart "Viktor" supernatural
        """
        from .character_templates import get_template
        
        template = get_template(genre)
        
        character_data = {
            "name": name,
            "description": template["description"],
            "owner_id": str(ctx.author.id),
            "traits": template["fields"].get("traits", []),
            "languages": template["fields"].get("languages", []),
            "inventory": template["fields"].get("inventory", []),
            "goals": template["fields"].get("goals", []),
            "species": template["fields"].get("species", None),
            "occupation": template["fields"].get("occupation", None),
            "relationships": {
                "ally": [],
                "rival": [],
                "neutral": [],
                "family": []
            }
        }
        
        # Add any genre-specific fields
        if "true_age" in template["fields"]:
            character_data["true_age"] = template["fields"]["true_age"]
        if "age_appearance" in template["fields"]:
            character_data["age_appearance"] = template["fields"]["age_appearance"]
        
        existing = await self.config.guild(ctx.guild).characters.get_raw(name, default=None)
        if existing:
            embed = discord.Embed(
                title="❌ Character Exists",
                description=f"A character named **{name}** already exists.",
                color=0xF04747
            )
            await ctx.send(embed=embed)
            return
        
        await self.config.guild(ctx.guild).characters.set_raw(name, value=character_data)
        
        embed = discord.Embed(
            title=f"✨ Quick Character Created: {name}",
            description=(
                f"Your {genre} character has been created with a basic template!\n\n"
                "Use the following commands to add more details:\n"
                f"• `[p]fable character edit {name} background \"Your character's story...\"`\n"
                f"• `[p]fable character edit {name} quote \"A memorable quote\"`\n"
                f"• `[p]fable character edit {name} image_url \"URL to character image\"`"
            ),
            color=0x43B581
        )
        
        if character_data["traits"]:
            embed.add_field(
                name="Starting Traits",
                value="\n".join(f"• {t}" for t in character_data["traits"]),
                inline=False
            )
            
        if character_data["inventory"]:
            embed.add_field(
                name="Starting Inventory",
                value="\n".join(f"• {i}" for i in character_data["inventory"]),
                inline=False
            )
            
        if character_data["goals"]:
            embed.add_field(
                name="Starting Goals",
                value="\n".join(f"• {g}" for g in character_data["goals"]),
                inline=False
            )
            
        embed.set_footer(text="Fable RP Tracker • Quick Character Creation", icon_url="https://cdn-icons-png.flaticon.com/512/3336/3336643.png")
        await ctx.send(embed=embed)

    @milestone.command(name="add", description="Add a character development milestone.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def milestone_add(
        self, 
        ctx: commands.Context,
        character: str,
        category: str,
        title: str,
        *,
        description: str
    ):
        """
        Record a character development milestone.

        Parameters
        ----------
        character: str
            The character's name
        category: str
            Type of milestone (Personal Growth/Relationship/Story/etc)
        title: str
            Short title for the milestone
        description: str
            Detailed description of the milestone
        """
        guild = ctx.guild
        char_data = await self.config.guild(guild).characters.get_raw(character, default=None)
        if not char_data:
            await ctx.send(f"❌ Character '{character}' not found.")
            return

        settings = await self.config.guild(guild).settings()
        valid_categories = settings.get("milestone_categories", [])
        if valid_categories and category.title() not in valid_categories:
            categories_str = "\n".join(f"• {c}" for c in valid_categories)
            await ctx.send(f"❌ Invalid category. Please use one of:\n{categories_str}")
            return

        milestones = await self.config.guild(guild).milestones()
        if character not in milestones:
            milestones[character] = []

        milestone_data = {
            "category": category.title(),
            "title": title,
            "description": description,
            "date": discord.utils.utcnow().isoformat(),
            "added_by": str(ctx.author.id)
        }
        
        milestones[character].append(milestone_data)
        await self.config.guild(guild).milestones.set(milestones)

        embed = discord.Embed(
            title=f"🎯 Milestone Added: {title}",
            description=description,
            color=0x43B581
        )
        embed.set_author(name=f"{character} - Character Development")
        embed.add_field(name="Category", value=category.title(), inline=True)
        embed.add_field(name="Recorded by", value=ctx.author.display_name, inline=True)
        embed.set_footer(text="Fable RP Tracker • Character Development")
        await ctx.send(embed=embed)

    @milestone.command(name="list", description="List a character's development milestones.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def milestone_list(
        self, 
        ctx: commands.Context,
        character: str,
        category: Optional[str] = None
    ):
        """
        View a character's development milestones.

        Parameters
        ----------
        character: str
            The character's name
        category: Optional[str]
            Filter by milestone category
        """
        guild = ctx.guild
        milestones = await self.config.guild(guild).milestones()
        char_milestones = milestones.get(character, [])

        if not char_milestones:
            await ctx.send(f"No milestones recorded for {character}.")
            return

        if category:
            category = category.title()
            char_milestones = [m for m in char_milestones if m["category"] == category]

        embed = discord.Embed(
            title=f"📈 {character}'s Development Timeline",
            color=0x7289DA
        )

        for milestone in reversed(char_milestones[-10:]):  # Show last 10 milestones
            date = discord.utils.parse_time(milestone["date"])
            embed.add_field(
                name=f"[{milestone['category']}] {milestone['title']}",
                value=f"📅 {date.strftime('%Y-%m-%d')}\n{milestone['description']}",
                inline=False
            )

        if len(char_milestones) > 10:
            total = len(char_milestones)
            embed.set_footer(text=f"Showing latest 10 of {total} milestones • Fable RP Tracker")
        else:
            embed.set_footer(text="Fable RP Tracker • Character Development")

        await ctx.send(embed=embed)

    @milestone.command(name="categories", description="List or modify milestone categories.")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def milestone_categories(
        self, 
        ctx: commands.Context,
        action: Optional[str] = None,
        *,
        category: Optional[str] = None
    ):
        """
        View or modify milestone categories.

        Parameters
        ----------
        action: Optional[str]
            'add' or 'remove' to modify categories
        category: Optional[str]
            Category name to add or remove
        """
        settings = await self.config.guild(ctx.guild).settings()
        categories = settings.get("milestone_categories", [])

        if not action:
            embed = discord.Embed(
                title="📊 Milestone Categories",
                description="\n".join(f"• {c}" for c in categories),
                color=0x7289DA
            )
            embed.set_footer(text="Fable RP Tracker • Development Categories")
            await ctx.send(embed=embed)
            return

        action = action.lower()
        if action == "add" and category:
            if category.title() not in categories:
                categories.append(category.title())
                settings["milestone_categories"] = categories
                await self.config.guild(ctx.guild).settings.set(settings)
                await ctx.send(f"✅ Added milestone category: {category.title()}")
            else:
                await ctx.send("That category already exists.")

        elif action == "remove" and category:
            if category.title() in categories:
                categories.remove(category.title())
                settings["milestone_categories"] = categories
                await self.config.guild(ctx.guild).settings.set(settings)
                await ctx.send(f"✅ Removed milestone category: {category.title()}")
            else:
                await ctx.send("That category doesn't exist.")

    @location.command(name="create", description="Create a new RP location.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def location_create(
        self,
        ctx: commands.Context,
        name: str,
        category: str,
        *,
        description: str
    ):
        """
        Create a new location for RP scenes.

        Parameters
        ----------
        name: str
            Name of the location
        category: str
            Type of location (tavern/castle/house/etc)
        description: str
            Description of the location
        """
        guild = ctx.guild
        locations = await self.config.guild(guild).locations()
        
        if name in locations:
            await ctx.send("❌ A location with that name already exists.")
            return

        location_data = {
            "name": name,
            "category": category,
            "description": description,
            "created_by": str(ctx.author.id),
            "created_at": discord.utils.utcnow().isoformat(),
            "visits": [],  # Track character visits
            "events": [],  # Track events that occurred here
            "connected_to": []  # Track connected locations
        }
        
        locations[name] = location_data
        await self.config.guild(guild).locations.set(locations)

        embed = discord.Embed(
            title=f"🏰 Location Created: {name}",
            description=description,
            color=0x43B581
        )
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Created by", value=ctx.author.display_name, inline=True)
        embed.set_footer(text="Fable RP Tracker • Locations")
        await ctx.send(embed=embed)

    @location.command(name="visit", description="Record a character's visit to a location.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def location_visit(
        self,
        ctx: commands.Context,
        location: str,
        character: str,
        *,
        note: Optional[str] = None
    ):
        """
        Record a character visiting a location.

        Parameters
        ----------
        location: str
            Name of the location
        character: str
            Name of the visiting character
        note: Optional[str]
            Optional note about the visit
        """
        guild = ctx.guild
        locations = await self.config.guild(guild).locations()
        characters = await self.config.guild(guild).characters()
        
        if location not in locations:
            await ctx.send("❌ Location not found.")
            return
            
        if character not in characters:
            await ctx.send("❌ Character not found.")
            return
            
        visit_data = {
            "character": character,
            "timestamp": discord.utils.utcnow().isoformat(),
            "note": note,
            "recorded_by": str(ctx.author.id)
        }
        
        locations[location]["visits"].append(visit_data)
        await self.config.guild(guild).locations.set(locations)

        embed = discord.Embed(
            title="📍 Location Visit Recorded",
            description=f"**{character}** visited *{location}*",
            color=0x43B581
        )
        if note:
            embed.add_field(name="Note", value=note, inline=False)
        embed.set_footer(text="Fable RP Tracker • Location Visit")
        await ctx.send(embed=embed)

    @location.command(name="connect", description="Connect two locations together.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def location_connect(
        self,
        ctx: commands.Context,
        location1: str,
        location2: str,
        *,
        description: Optional[str] = None
    ):
        """
        Create a connection between two locations.

        Parameters
        ----------
        location1: str
            First location name
        location2: str
            Second location name
        description: Optional[str]
            Description of how they're connected
        """
        guild = ctx.guild
        locations = await self.config.guild(guild).locations()
        
        if location1 not in locations or location2 not in locations:
            await ctx.send("❌ One or both locations not found.")
            return
            
        connection = {
            "location": location2,
            "description": description,
            "connected_at": discord.utils.utcnow().isoformat(),
            "connected_by": str(ctx.author.id)
        }
        
        if connection not in locations[location1]["connected_to"]:
            locations[location1]["connected_to"].append(connection)
            # Add reverse connection
            reverse_connection = {
                "location": location1,
                "description": description,
                "connected_at": discord.utils.utcnow().isoformat(),
                "connected_by": str(ctx.author.id)
            }
            locations[location2]["connected_to"].append(reverse_connection)
            
        await self.config.guild(guild).locations.set(locations)

        embed = discord.Embed(
            title="🔗 Locations Connected",
            description=f"Connected **{location1}** to **{location2}**",
            color=0x43B581
        )
        if description:
            embed.add_field(name="Connection Details", value=description, inline=False)
        embed.set_footer(text="Fable RP Tracker • Location Connection")
        await ctx.send(embed=embed)

    @location.command(name="info", description="View location details and history.")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def location_info(
        self,
        ctx: commands.Context,
        name: str
    ):
        """
        View detailed information about a location.

        Parameters
        ----------
        name: str
            Name of the location
        """
        guild = ctx.guild
        locations = await self.config.guild(guild).locations()
        
        if name not in locations:
            await ctx.send("❌ Location not found.")
            return
            
        location = locations[name]
        
        embed = discord.Embed(
            title=f"🏰 {name}",
            description=location["description"],
            color=0x7289DA
        )
        
        embed.add_field(name="Category", value=location["category"], inline=True)
        
        # Recent visits
        if location["visits"]:
            recent_visits = sorted(location["visits"], key=lambda v: v["timestamp"], reverse=True)[:5]
            visits_text = ""
            for visit in recent_visits:
                timestamp = discord.utils.parse_time(visit["timestamp"])
                visits_text += f"• {visit['character']} ({timestamp.strftime('%Y-%m-%d')})\n"
            embed.add_field(name="Recent Visits", value=visits_text or "No visits recorded", inline=False)
        
        # Connected locations
        if location["connected_to"]:
            connections = ""
            for conn in location["connected_to"]:
                connections += f"• {conn['location']}"
                if conn.get("description"):
                    connections += f" - {conn['description']}"
                connections += "\n"
            embed.add_field(name="Connected Locations", value=connections, inline=False)
        
        # Events
        if location["events"]:
            events_text = ""
            for event in sorted(location["events"], key=lambda e: e["timestamp"], reverse=True)[:3]:
                timestamp = discord.utils.parse_time(event["timestamp"])
                events_text += f"• {event['title']} ({timestamp.strftime('%Y-%m-%d')})\n"
            embed.add_field(name="Recent Events", value=events_text, inline=False)

        embed.set_footer(text="Fable RP Tracker • Location Info")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fable(bot))
