"""A persistent, button-driven dungeon crawler for Red-DiscordBot."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import json
import logging
import random
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import discord
from redbot.core import Config, bank, commands
from redbot.core.utils.chat_formatting import humanize_list

from .advanced_content import (
    BACKGROUNDS,
    BLESSINGS,
    ITEM_SETS,
    NPCS,
    SCARS,
    SUBCLASSES,
    TALENT_TREES,
    TITLES,
)
from .content import (
    ACHIEVEMENTS,
    AFFIXES,
    CHOICES,
    GAME_CLASSES,
    LORE_FRAGMENTS,
    MATERIALS,
    RARITIES,
    apply_affix,
    boss_for_floor,
    enemy_for_floor,
    generate_item,
    item_stat_line,
    region_for_floor,
    xp_for_level,
)
from .dashboard_integration import DashboardIntegration
from .expansion_content import CAMPAIGN_CHAPTERS, COMPANIONS, PROFESSIONS, TOWN_BUILDINGS
from .living_content import FACTIONS, LIVING_RECIPES, LIVING_TITLES, NAMED_DUNGEONS, TENETS
from .loot_content import CONSUMABLES, RECIPES, STORY_RELICS
from .persistent_views import (
    DeepDelveDynamicButton,
    DeepDelveDynamicSelect,
    persistent_custom_id,
)
from .systems import (
    QUESTS,
    SANCTUM_ROOMS,
    abandon_dungeon,
    accept_commission,
    accept_oath,
    accept_quest,
    active_companion,
    active_world_event,
    advance_campaign,
    advance_dungeon,
    advance_living_campaign,
    advance_redemption,
    advance_season_chapter,
    apply_advanced_itemization,
    apply_miniboss,
    arena_power,
    atlas_locations,
    available_abilities,
    available_quests,
    begin_redemption,
    begin_season_chapter,
    boss_relic_for,
    campaign_bonuses,
    campaign_scene,
    change_relationship,
    commission_board,
    companion_bonuses,
    comparison_line,
    content_counts,
    create_nemesis,
    create_rumor,
    create_starter_item,
    current_season,
    daily_dungeon,
    defeat_nemesis,
    dismantle_rewards,
    ending_recap,
    ensure_enemy_intent,
    ensure_legacy,
    ensure_nemeses,
    ensure_relationships,
    ensure_sanctum,
    enter_dungeon,
    equip_tenets,
    equipment_effects,
    equipment_set_bonuses,
    fail_quest,
    floor_mutator,
    gather,
    generate_mail,
    give_gift,
    grant_companion_xp,
    grant_profession_xp,
    grant_resolve,
    guild_perks,
    intent_description,
    item_detail,
    item_power,
    item_sale_value,
    living_campaign_view,
    moral_power,
    morality_path,
    npc_moral_reaction,
    npc_progress,
    oath_board,
    origin_morality,
    party_bonus,
    profession_rank,
    progress_commission,
    progress_oath,
    progress_quests,
    progress_rumor,
    progression_bonuses,
    record_bestiary_kill,
    record_choice_deed,
    record_dungeon_victory,
    record_nemesis_escape,
    refresh_titles,
    relationship_level,
    request_favor,
    research_recipe,
    resolve_dungeon_choice,
    resolve_quest,
    restore_challenge_origin,
    roll_consumable,
    roll_enemy_intent,
    sanctum_upgrade_cost,
    scaled_daily_floor,
    season_chapter_status,
    short_code,
    should_auto_dismantle,
    starter_options,
    subclass_options,
    tenet_effects,
    town_bonuses,
    unlock_companions,
    unlock_tenet,
    upgrade_building,
    upgrade_cost,
    upgrade_sanctum,
    use_consumable,
    use_faction_service,
    use_moral_power,
    validate_content,
    world_echoes,
)
from .systems.migrations import GUILD_SCHEMA_VERSION, PROFILE_SCHEMA_VERSION, migrate_guild, migrate_profile
from .systems.progression import talent_definition
from .systems.puzzles import puzzle_for_floor, resolve_puzzle

if TYPE_CHECKING:
    from redbot.core.bot import Red

EMBED_COLOR = 0x6C3483
SUCCESS_COLOR = 0x2ECC71
DANGER_COLOR = 0xC0392B
GOLD_COLOR = 0xF1C40F
LOGGER = logging.getLogger("red.taakoscogs.deepdelve")
TITLES = {**TITLES, **LIVING_TITLES}


def progress_bar(current: int, maximum: int, length: int = 10) -> str:
    """Render a compact, safe progress bar."""
    maximum = max(1, maximum)
    filled = max(0, min(length, round(length * max(0, current) / maximum)))
    return "█" * filled + "░" * (length - filled)


class OwnedView(discord.ui.View):
    """A view that only its owning player may use."""

    def __init__(
        self,
        cog: DeepDelve,
        user_id: int,
        *,
        timeout: float | None = None,
        persistent: bool = True,
    ) -> None:
        super().__init__(timeout=None if persistent else timeout)
        self.cog = cog
        self.user_id = user_id
        self.persistent = persistent
        declared_children = list(self.children)
        self.clear_items()
        for child in declared_children:
            self.add_item(child)

    def add_item(self, item: discord.ui.Item[Any]) -> OwnedView:
        """Add a component and bind a stable owner-specific custom ID."""
        super().add_item(self._bind_component(item))
        return self

    def _bind_component(self, item: discord.ui.Item[Any]) -> discord.ui.Item[Any]:
        if not self.persistent or not isinstance(item, (discord.ui.Button, discord.ui.Select)):
            return item
        existing = item.custom_id or ""
        if existing.startswith(("deepdelve:choice:", "deepdelve:puzzle:", "deepdelve:campaign:")):
            route = existing.removeprefix("deepdelve:")
        elif isinstance(item, discord.ui.Select):
            route = {
                "ClassSelect": "class_select",
                "AbilitySelect": "ability_select",
                "ConsumableSelect": "consumable_select",
                "InventorySelect": "inventory_select",
                "OriginBackgroundSelect": "origin_background",
                "OriginStarterSelect": "origin_starter",
                "OriginAlignmentSelect": "origin_alignment",
                "ProfessionSelect": "profession_select",
                "CompanionSelect": "companion_select",
                "CommissionSelect": "commission_select",
                "QuestActionSelect": "quest_action_select",
                "AtlasActionSelect": "atlas_action_select",
                "ArchiveChapterSelect": "archive_chapter_select",
            }.get(type(item).__name__, type(item).__name__.lower())
        else:
            callback = getattr(item.callback, "callback", item.callback)
            callback_name = getattr(callback, "__name__", "unknown")
            view_name = type(self).__name__.removesuffix("View").lower()
            route = f"{view_name}:{callback_name}"
        kind = "b" if isinstance(item, discord.ui.Button) else "s"
        item.custom_id = persistent_custom_id(kind, self.user_id, route)
        if isinstance(item, discord.ui.Button):
            return DeepDelveDynamicButton(item, self.user_id, route)
        return DeepDelveDynamicSelect(item, self.user_id, route)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "This adventure belongs to another delver. Use `/deepdelve adventure` to open yours.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
    ) -> None:
        """Acknowledge component failures so Discord does not show a silent timeout."""
        if isinstance(error, discord.InteractionResponded):
            LOGGER.debug("Ignored duplicate DeepDelve response for %s", type(item).__name__)
            return
        LOGGER.error(
            "DeepDelve view callback failed for %s",
            type(item).__name__,
            exc_info=(type(error), error, error.__traceback__),
        )
        await self.cog._persistent_error(
            interaction,
            "DeepDelve hit an unexpected snag. Your progress is safe; reopen the current screen and try again.",
        )


class ClassSelect(discord.ui.Select):
    """Character class selector."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=details["name"],
                value=key,
                emoji=details["emoji"],
                description=details["description"][:100],
            )
            for key, details in GAME_CLASSES.items()
        ]
        super().__init__(placeholder="Choose your path…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, ClassSelectView) or not interaction.guild:
            return
        class_key = self.values[0]
        await interaction.response.defer()
        created = await view.cog._create_character(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.display_name,
            class_key,
        )
        if not created:
            await interaction.followup.send(
                "You already have a character. Use `/deepdelve retire` before starting over.",
                ephemeral=True,
            )
            return
        profile = await view.cog._get_profile(interaction.guild.id, interaction.user.id)
        embed = view.cog._origin_embed(profile)
        await interaction.edit_original_response(
            embed=embed,
            view=OriginView(view.cog, interaction.user.id, profile),
        )


class ClassSelectView(OwnedView):
    """View used during character creation."""

    def __init__(self, cog: DeepDelve, user_id: int) -> None:
        super().__init__(cog, user_id, timeout=300)
        self.add_item(ClassSelect())


class OriginBackgroundSelect(discord.ui.Select):
    """Choose a background during the origin sequence."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="1. Choose your background…",
            options=[
                discord.SelectOption(
                    label=details["name"],
                    value=key,
                    emoji=details["emoji"],
                    description=details["description"][:100],
                )
                for key, details in BACKGROUNDS.items()
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, OriginView):
            await view.cog._origin_interaction(interaction, "background", self.values[0])


class OriginStarterSelect(discord.ui.Select):
    """Choose a class-specific starter weapon."""

    def __init__(self, class_key: str) -> None:
        super().__init__(
            placeholder="2. Choose your origin weapon…",
            options=[
                discord.SelectOption(
                    label=details["name"],
                    value=key,
                    emoji=details["emoji"],
                    description=details["description"][:100],
                )
                for key, details in starter_options(class_key).items()
            ],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, OriginView):
            await view.cog._origin_interaction(interaction, "starter", self.values[0])


class OriginAlignmentSelect(discord.ui.Select):
    """Choose an alignment during the origin sequence."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="3. Choose your alignment…",
            options=[
                discord.SelectOption(label="Radiant", value="Radiant", emoji="☀️", description="Mercy, hope, and truth."),
                discord.SelectOption(
                    label="Pragmatic",
                    value="Pragmatic",
                    emoji="⚖️",
                    description="Survival, balance, and consequence.",
                ),
                discord.SelectOption(label="Umbral", value="Umbral", emoji="🌑", description="Power, secrecy, and ambition."),
            ],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, OriginView):
            await view.cog._origin_interaction(interaction, "alignment", self.values[0])


class OriginView(OwnedView):
    """Persistent character-origin controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.add_item(OriginBackgroundSelect())
        self.add_item(OriginStarterSelect(profile["class_key"]))
        self.add_item(OriginAlignmentSelect())

    @discord.ui.button(label="Begin the Descent", emoji="🕯️", style=discord.ButtonStyle.success, row=3)
    async def begin(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._origin_begin(interaction)


class AdventureView(OwnedView):
    """Primary exploration controls."""

    @discord.ui.button(label="Explore", emoji="🧭", style=discord.ButtonStyle.primary)
    async def explore(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._handle_explore_interaction(interaction)

    @discord.ui.button(label="Character", emoji="🧑‍🚀", style=discord.ButtonStyle.secondary)
    async def character(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._profile_embed(interaction.user, profile),
            view=AdventureView(self.cog, self.user_id),
        )

    @discord.ui.button(label="Inventory", emoji="🎒", style=discord.ButtonStyle.secondary)
    async def inventory(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._show_inventory_interaction(interaction)

    @discord.ui.button(label="Town", emoji="🏘️", style=discord.ButtonStyle.success)
    async def town(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._town_embed(profile),
            view=TownView(self.cog, self.user_id),
        )

    @discord.ui.button(label="Game Hub", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def game_hub(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "hub")


class GameHubView(OwnedView):
    """Persistent browser-RPG navigation rendered from current profile state."""

    @discord.ui.button(label="Resume", emoji="🧭", style=discord.ButtonStyle.primary, row=0)
    async def resume(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "resume")

    @discord.ui.button(label="Quests", emoji="📜", style=discord.ButtonStyle.secondary, row=0)
    async def quests(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "quests")

    @discord.ui.button(label="Atlas", emoji="🗺️", style=discord.ButtonStyle.secondary, row=0)
    async def atlas(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "atlas")

    @discord.ui.button(label="Character", emoji="🧑‍🚀", style=discord.ButtonStyle.secondary, row=0)
    async def character(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "character")

    @discord.ui.button(label="Inventory", emoji="🎒", style=discord.ButtonStyle.secondary, row=0)
    async def inventory(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "inventory")

    @discord.ui.button(label="Morality", emoji="⚖️", style=discord.ButtonStyle.secondary, row=1)
    async def morality(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "morality")

    @discord.ui.button(label="Codex", emoji="📚", style=discord.ButtonStyle.secondary, row=1)
    async def codex(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "codex")

    @discord.ui.button(label="Town", emoji="🏘️", style=discord.ButtonStyle.success, row=1)
    async def town(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "town")

    @discord.ui.button(label="Mail", emoji="✉️", style=discord.ButtonStyle.secondary, row=1)
    async def mail(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "mail")

    @discord.ui.button(label="Sanctum", emoji="🏛️", style=discord.ButtonStyle.secondary, row=1)
    async def sanctum(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "sanctum")

    @discord.ui.button(label="Activities", emoji="🎯", style=discord.ButtonStyle.primary, row=2)
    async def activities(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class QuestActionSelect(discord.ui.Select):
    """Accept or resolve journal quests directly from the menu."""

    def __init__(self, profile: dict[str, Any]) -> None:
        state = profile.get("quests_v2", {})
        options = []
        for key, progress in state.get("active", {}).items():
            if int(progress.get("progress", 0)) < int(progress.get("target", 1)):
                continue
            definition = QUESTS.get(key, {})
            for outcome, emoji in (("mercy", "🤍"), ("honesty", "👁️"), ("ambition", "🔥"), ("ruthlessness", "🗡️")):
                options.append(
                    discord.SelectOption(
                        label=f"Resolve: {definition.get('name', key)}",
                        value=f"resolve|{key}|{outcome}",
                        emoji=emoji,
                        description=f"Choose the {outcome.title()} outcome.",
                    ),
                )
        if len(options) < 25:
            for quest in available_quests(profile):
                if (
                    quest["available"]
                    and not quest["active"]
                    and not quest["completed"]
                    and not quest.get("managed")
                ):
                    options.append(
                        discord.SelectOption(
                            label=f"Accept: {quest['name']}"[:100],
                            value=f"accept|{quest['key']}",
                            emoji="📜",
                            description=(
                                f"{quest['category'].title()} • target {quest['target']} • "
                                f"up to {quest['energy']} energy"
                            )[:100],
                        ),
                    )
                    if len(options) >= 25:
                        break
        super().__init__(placeholder="Accept or resolve a quest…", options=options[:25], row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, QuestJournalView):
            parts = self.values[0].split("|", maxsplit=2)
            await view.cog._quest_menu_interaction(
                interaction,
                parts[0],
                parts[1],
                parts[2] if len(parts) > 2 else "",
            )


class QuestJournalView(OwnedView):
    """Persistent menu-first quest journal."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        state = profile.get("quests_v2", {})
        has_ready = any(
            int(progress.get("progress", 0)) >= int(progress.get("target", 1))
            for progress in state.get("active", {}).values()
        )
        has_available = any(
            quest["available"] and not quest["active"] and not quest["completed"] and not quest.get("managed")
            for quest in available_quests(profile)
        )
        if has_ready or has_available:
            self.add_item(QuestActionSelect(profile))

    @discord.ui.button(label="Game Hub", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "hub")


class AtlasActionSelect(discord.ui.Select):
    """Enter a dungeon or resolve its current room choice."""

    def __init__(self, profile: dict[str, Any]) -> None:
        run = profile.get("atlas", {}).get("active_dungeon") or {}
        pending = run.get("pending") or {}
        if pending:
            options = [
                discord.SelectOption(
                    label=f"Choose {option.title()}",
                    value=f"choice|{option}",
                    emoji={"mercy": "🤍", "honesty": "👁️", "ambition": "🔥", "ruthlessness": "🗡️"}.get(
                        option,
                        "🧩",
                    ),
                    description=f"Resolve {pending['name']} through this approach.",
                )
                for option in pending["options"]
            ]
            placeholder = "Resolve the current room…"
        else:
            options = [
                discord.SelectOption(
                    label=location["name"],
                    value=f"enter|{location['key']}",
                    emoji="🏛️",
                    description=(
                        f"Floor {location['floor']} • {location['rooms']} rooms • "
                        f"{location['energy_per_room']} energy/room"
                    )[:100],
                )
                for location in atlas_locations(profile)
                if location["discovered"] and not run
            ][:25]
            placeholder = "Enter a named dungeon…"
        super().__init__(placeholder=placeholder, options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, AtlasView):
            action, value = self.values[0].split("|", maxsplit=1)
            await view.cog._atlas_menu_interaction(interaction, action, value)


class AtlasView(OwnedView):
    """Persistent named-dungeon controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        run = profile.get("atlas", {}).get("active_dungeon") or {}
        pending = run.get("pending") or {}
        has_locations = any(location["discovered"] for location in atlas_locations(profile))
        if pending or (not run and has_locations):
            self.add_item(AtlasActionSelect(profile))
        self.advance.disabled = not bool(run) or bool(pending) or bool(profile.get("encounter"))
        self.abandon.disabled = not bool(run) or bool(profile.get("encounter"))
        self.resume.disabled = not bool(profile.get("encounter"))

    @discord.ui.button(label="Advance (1 Energy)", emoji="🧭", style=discord.ButtonStyle.primary, row=1)
    async def advance(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._atlas_menu_interaction(interaction, "advance", "")

    @discord.ui.button(label="Resume Battle", emoji="⚔️", style=discord.ButtonStyle.danger, row=1)
    async def resume(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "resume")

    @discord.ui.button(label="Abandon", emoji="🏳️", style=discord.ButtonStyle.secondary, row=1)
    async def abandon(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._atlas_menu_interaction(interaction, "abandon", "")

    @discord.ui.button(label="Game Hub", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "hub")


class SagaView(OwnedView):
    """Persistent Living Chronicle scene and conviction controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        state = living_campaign_view(profile)
        complete = bool(state["complete"])
        needs_choice = bool(not complete and state["needs_choice"])
        available = bool(not complete and state["available"])
        self.continue_story.disabled = not available or needs_choice
        for button in (self.mercy, self.honesty, self.ambition, self.ruthlessness):
            button.disabled = not available or not needs_choice

    @discord.ui.button(label="Continue (1 Energy)", emoji="📖", style=discord.ButtonStyle.primary, row=0)
    async def continue_story(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._saga_menu_interaction(interaction, "")

    @discord.ui.button(label="Mercy", emoji="🤍", style=discord.ButtonStyle.success, row=1)
    async def mercy(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._saga_menu_interaction(interaction, "mercy")

    @discord.ui.button(label="Honesty", emoji="👁️", style=discord.ButtonStyle.secondary, row=1)
    async def honesty(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._saga_menu_interaction(interaction, "honesty")

    @discord.ui.button(label="Ambition", emoji="🔥", style=discord.ButtonStyle.primary, row=1)
    async def ambition(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._saga_menu_interaction(interaction, "ambition")

    @discord.ui.button(label="Ruthlessness", emoji="🗡️", style=discord.ButtonStyle.danger, row=1)
    async def ruthlessness(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._saga_menu_interaction(interaction, "ruthlessness")

    @discord.ui.button(label="Activities", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class ArchiveChapterSelect(discord.ui.Select):
    """Begin any available, unfinished seasonal chapter."""

    def __init__(self, profile: dict[str, Any]) -> None:
        options = [
            discord.SelectOption(
                label=f"{chapter['index']}. {chapter['name']}"[:100],
                value=str(chapter["index"]),
                emoji="📚",
                description="Begin this permanent three-scene chapter.",
            )
            for chapter in season_chapter_status(profile)
            if chapter["available"] and not chapter["completed"] and not chapter["active"]
        ][:25]
        super().__init__(placeholder="Begin an available chapter…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, SeasonArchiveView):
            await view.cog._archive_menu_interaction(interaction, "begin", int(self.values[0]))


class SeasonArchiveView(OwnedView):
    """Persistent seasonal archive controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        active = profile.get("season_story", {}).get("active", "")
        available = any(
            chapter["available"] and not chapter["completed"] and not chapter["active"]
            for chapter in season_chapter_status(profile)
        )
        if not active and available:
            self.add_item(ArchiveChapterSelect(profile))
        self.advance.disabled = not bool(active)
        if active:
            scene = int(profile.get("season_story", {}).get("scene", 0))
            self.advance.label = f"Advance ({(3, 3, 2)[scene]} Energy)"

    @discord.ui.button(label="Advance Chapter", emoji="📖", style=discord.ButtonStyle.primary, row=1)
    async def advance(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._archive_menu_interaction(interaction, "advance", 0)

    @discord.ui.button(label="Activities", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class ActivitiesView(OwnedView):
    """Menu-first access to systems that previously required commands."""

    @discord.ui.button(label="Profession", emoji="🛠️", style=discord.ButtonStyle.primary, row=0)
    async def profession(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "profession")

    @discord.ui.button(label="Companions", emoji="🐾", style=discord.ButtonStyle.secondary, row=0)
    async def companions(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "companions")

    @discord.ui.button(label="Commissions", emoji="⚒️", style=discord.ButtonStyle.secondary, row=0)
    async def commissions(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "commissions")

    @discord.ui.button(label="Living Saga", emoji="📖", style=discord.ButtonStyle.secondary, row=1)
    async def saga(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "saga")

    @discord.ui.button(label="Season Archive", emoji="🗄️", style=discord.ButtonStyle.secondary, row=1)
    async def archive(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "archive")

    @discord.ui.button(label="Game Hub", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "hub")


class ProfessionSelect(discord.ui.Select):
    """Choose or change a profession without typing its key."""

    def __init__(self, profile: dict[str, Any]) -> None:
        current = profile.get("profession", {}).get("key", "")
        options = [
            discord.SelectOption(
                label=definition["name"],
                value=key,
                emoji=definition["emoji"],
                description=definition["benefit"][:100],
                default=key == current,
            )
            for key, definition in PROFESSIONS.items()
        ]
        super().__init__(placeholder="Choose or change profession…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, ProfessionView):
            await view.cog._profession_select_interaction(interaction, self.values[0])


class ProfessionView(OwnedView):
    """Profession selection and daily work controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.add_item(ProfessionSelect(profile))

    @discord.ui.button(label="Gather", emoji="⛏️", style=discord.ButtonStyle.success, row=1)
    async def gather(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._profession_gather_interaction(interaction)

    @discord.ui.button(label="Commissions", emoji="📋", style=discord.ButtonStyle.primary, row=1)
    async def commissions(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "commissions")

    @discord.ui.button(label="Activities", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class CompanionSelect(discord.ui.Select):
    """Activate a discovered companion."""

    def __init__(self, profile: dict[str, Any]) -> None:
        active_key = profile.get("active_companion", "")
        options = [
            discord.SelectOption(
                label=COMPANIONS[key]["name"],
                value=key,
                emoji=COMPANIONS[key]["emoji"],
                description=COMPANIONS[key]["passive"][:100],
                default=key == active_key,
            )
            for key in profile.get("companions", {})
            if key in COMPANIONS
        ][:25]
        if not options:
            options = [
                discord.SelectOption(
                    label="No companions discovered",
                    value="none",
                    emoji="🔒",
                    description="Continue descending to meet companions.",
                ),
            ]
        super().__init__(placeholder="Choose active companion…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CompanionView):
            await view.cog._companion_select_interaction(interaction, self.values[0])


class CompanionView(OwnedView):
    """Companion roster controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.add_item(CompanionSelect(profile))

    @discord.ui.button(label="Activities", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class CommissionSelect(discord.ui.Select):
    """Accept one of the current weekly commissions."""

    def __init__(self, profile: dict[str, Any]) -> None:
        offers = commission_board(profile)
        options = [
            discord.SelectOption(
                label=f"{index}. {offer['name']}",
                value=str(index),
                emoji="📋",
                description=(
                    f"{offer['objective'].title()} {offer['target']} • "
                    f"{offer['reward']['gold']} currency"
                )[:100],
            )
            for index, offer in enumerate(offers, start=1)
        ]
        super().__init__(
            placeholder="Accept a weekly commission…",
            options=options,
            disabled=bool(profile.get("commissions", {}).get("active")),
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CommissionsView):
            await view.cog._commission_select_interaction(interaction, int(self.values[0]))


class CommissionsView(OwnedView):
    """Weekly commission board controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.add_item(CommissionSelect(profile))

    @discord.ui.button(label="Profession", emoji="🛠️", style=discord.ButtonStyle.primary, row=1)
    async def profession(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "profession")

    @discord.ui.button(label="Activities", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "activities")


class AbilitySelect(discord.ui.Select):
    """Select one of the character's unlocked combat abilities."""

    def __init__(self, profile: dict[str, Any]) -> None:
        cooldowns = profile.get("skill_cooldowns", {})
        options = []
        for ability in available_abilities(profile):
            remaining = int(cooldowns.get(ability["key"], 0))
            suffix = f" • Cooldown {remaining}" if remaining else ""
            options.append(
                discord.SelectOption(
                    label=ability["name"],
                    value=ability["key"],
                    emoji=ability["emoji"],
                    description=(f"{ability['mana']} mana • {ability['description']}{suffix}")[:100],
                ),
            )
        super().__init__(placeholder="Choose an ability…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CombatView):
            await view.cog._combat_interaction(interaction, f"ability:{self.values[0]}")


class ConsumableSelect(discord.ui.Select):
    """Use one of the delver's carried tactical items."""

    def __init__(self, profile: dict[str, Any]) -> None:
        options = [
            discord.SelectOption(
                label=f"{CONSUMABLES[key]['name']} ×{amount}",
                value=key,
                emoji=CONSUMABLES[key]["emoji"],
                description=CONSUMABLES[key]["description"][:100],
            )
            for key, amount in profile.get("consumables", {}).items()
            if amount > 0 and key in CONSUMABLES
        ][:25]
        super().__init__(placeholder="Use a tactical item…", options=options, row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CombatView):
            await view.cog._combat_interaction(interaction, f"consumable:{self.values[0]}")


class CombatView(OwnedView):
    """Turn-based combat controls with an ability selector."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.add_item(AbilitySelect(profile))
        if any(amount > 0 for amount in profile.get("consumables", {}).values()):
            self.add_item(ConsumableSelect(profile))
        power = moral_power(profile)
        if power["available"]:
            self.conviction.label = power["name"]
        elif power["unlocked"] and power["fatigue"]:
            self.conviction.label = f"Fatigue: {power['fatigue']} victories"
        else:
            self.conviction.label = "Conviction Locked"
        self.conviction.emoji = power["emoji"] if power["unlocked"] else "🔒"
        self.conviction.disabled = not power["available"]

    @discord.ui.button(label="Attack", emoji="⚔️", style=discord.ButtonStyle.danger, row=1)
    async def attack(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._combat_interaction(interaction, "attack")

    @discord.ui.button(label="Defend", emoji="🛡️", style=discord.ButtonStyle.primary, row=1)
    async def defend(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._combat_interaction(interaction, "defend")

    @discord.ui.button(label="Potion", emoji="🧪", style=discord.ButtonStyle.success, row=1)
    async def potion(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._combat_interaction(interaction, "potion")

    @discord.ui.button(label="Flee", emoji="💨", style=discord.ButtonStyle.secondary, row=1)
    async def flee(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._combat_interaction(interaction, "flee")

    @discord.ui.button(label="Conviction", emoji="⚖️", style=discord.ButtonStyle.secondary, row=3)
    async def conviction(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._combat_interaction(interaction, "conviction")


class TownView(OwnedView):
    """Town service controls."""

    @discord.ui.button(label="Rest", emoji="🛏️", style=discord.ButtonStyle.success, row=0)
    async def rest(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._town_interaction(interaction, "rest")

    @discord.ui.button(label="Buy Potion", emoji="🧪", style=discord.ButtonStyle.primary, row=0)
    async def potion(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._town_interaction(interaction, "potion")

    @discord.ui.button(label="Meditate", emoji="🕯️", style=discord.ButtonStyle.primary, row=0)
    async def meditate(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._town_interaction(interaction, "meditate")

    @discord.ui.button(label="Contract", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def contract(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._contract_interaction(interaction)

    @discord.ui.button(label="Forge", emoji="⚒️", style=discord.ButtonStyle.secondary, row=1)
    async def forge(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._show_crafting_interaction(interaction)

    @discord.ui.button(label="Profession", emoji="🛠️", style=discord.ButtonStyle.primary, row=1)
    async def profession(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._hub_interaction(interaction, "profession")

    @discord.ui.button(label="Return", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._adventure_embed(profile),
            view=AdventureView(self.cog, self.user_id),
        )


class ChoiceButton(discord.ui.Button):
    """One consequence-bearing narrative choice."""

    def __init__(self, action: str, label: str, emoji: str, row: int = 0) -> None:
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary if action != "leave" else discord.ButtonStyle.secondary,
            custom_id=f"deepdelve:choice:{action}",
            row=row,
        )
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, ChoiceView):
            await view.cog._choice_interaction(interaction, self.action)


class ChoiceView(OwnedView):
    """Dynamic controls for authored dungeon decisions."""

    def __init__(self, cog: DeepDelve, user_id: int, choice: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        for action, label, emoji in choice.get("options", ()):
            self.add_item(ChoiceButton(action, label, emoji))


class PuzzleButton(discord.ui.Button):
    """One possible answer to a dungeon puzzle."""

    def __init__(self, answer: str, label: str, row: int = 0) -> None:
        super().__init__(
            label=label[:80],
            style=discord.ButtonStyle.primary,
            custom_id=f"deepdelve:puzzle:{answer}",
            row=row,
        )
        self.answer = answer

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, PuzzleView):
            await view.cog._puzzle_interaction(interaction, self.answer)


class PuzzleView(OwnedView):
    """Buttons for an active dungeon riddle."""

    def __init__(self, cog: DeepDelve, user_id: int, puzzle: dict[str, Any]) -> None:
        super().__init__(cog, user_id, timeout=300)
        for index, (answer, label) in enumerate(puzzle.get("options", {}).items()):
            self.add_item(PuzzleButton(answer, label, index // 3))


class CampaignButton(discord.ui.Button):
    """One permanent campaign decision."""

    def __init__(self, action: str, label: str, row: int = 0) -> None:
        super().__init__(
            label=label[:80],
            style=discord.ButtonStyle.danger
            if action in {"power", "harvest", "ignite", "inherit"}
            else discord.ButtonStyle.primary,
            custom_id=f"deepdelve:campaign:{action}",
            row=row,
        )
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, CampaignView):
            await view.cog._campaign_interaction(interaction, self.action)


class CampaignView(OwnedView):
    """Buttons for permanent campaign decisions."""

    def __init__(self, cog: DeepDelve, user_id: int, options: dict[str, tuple[str, str]]) -> None:
        super().__init__(cog, user_id, timeout=300)
        for index, (action, (label, _consequence)) in enumerate(options.items()):
            self.add_item(CampaignButton(action, label, index // 3))


class CampaignContinueView(OwnedView):
    """Advance to the next authored campaign scene."""

    @discord.ui.button(label="Continue Story", emoji="📖", style=discord.ButtonStyle.primary)
    async def continue_story(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._campaign_interaction(interaction, None)


class CraftView(OwnedView):
    """Lastlight forge controls."""

    @discord.ui.button(label="Forge Weapon", emoji="⚔️", style=discord.ButtonStyle.danger)
    async def weapon(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._craft_interaction(interaction, "weapon")

    @discord.ui.button(label="Forge Armor", emoji="🛡️", style=discord.ButtonStyle.primary)
    async def armor(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._craft_interaction(interaction, "armor")

    @discord.ui.button(label="Forge Charm", emoji="📿", style=discord.ButtonStyle.success)
    async def charm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._craft_interaction(interaction, "charm")

    @discord.ui.button(label="Return", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._town_embed(profile),
            view=TownView(self.cog, self.user_id),
        )


class InventorySelect(discord.ui.Select):
    """Select an inventory item for management."""

    def __init__(self, profile: dict[str, Any]) -> None:
        inventory = profile.get("inventory", [])
        options = []
        for index, item in enumerate(inventory[:25], start=1):
            rarity = RARITIES[int(item.get("rarity_index", 0))]
            options.append(
                discord.SelectOption(
                    label=f"{index}. {item['name']}"[:100],
                    value=str(item["id"]),
                    emoji=rarity["emoji"],
                    description=item_stat_line(item)[:100],
                ),
            )
        if not options:
            options.append(
                discord.SelectOption(
                    label="Your pack is empty",
                    value="empty",
                    emoji="🎒",
                    description="Defeat enemies and explore treasure rooms to find gear.",
                ),
            )
        super().__init__(placeholder="Select an item…", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, InventoryView):
            return
        view.selected_id = self.values[0]
        await interaction.response.defer()
        if interaction.guild:
            profile = await view.cog._get_profile(interaction.guild.id, interaction.user.id)
            await interaction.edit_original_response(
                embed=view.cog._inventory_embed(profile, view.selected_id),
                view=view,
            )


class InventoryView(OwnedView):
    """Equipment management controls."""

    def __init__(self, cog: DeepDelve, user_id: int, profile: dict[str, Any]) -> None:
        super().__init__(cog, user_id)
        self.selected_id: str | None = None
        self.add_item(InventorySelect(profile))

    def bind_selection(self, selected_id: str) -> None:
        """Encode the selected item into action routes for stateless recovery."""
        self.selected_id = selected_id
        for child in self.children:
            if not isinstance(child, DeepDelveDynamicButton) or not child.custom_id:
                continue
            marker = f"deepdelve:b:{self.user_id}:inventory:"
            if not child.custom_id.startswith(marker):
                continue
            action = child.custom_id.removeprefix(marker).split(":", maxsplit=1)[0]
            if action != "back":
                child.custom_id = persistent_custom_id(
                    "b",
                    self.user_id,
                    f"inventory:{action}:{selected_id}",
                )

    @discord.ui.button(label="Equip", emoji="🛡️", style=discord.ButtonStyle.primary, row=1)
    async def equip(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "equip")

    @discord.ui.button(label="Upgrade", emoji="⬆️", style=discord.ButtonStyle.success, row=1)
    async def upgrade(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "upgrade")

    @discord.ui.button(label="Dismantle", emoji="🔨", style=discord.ButtonStyle.danger, row=1)
    async def dismantle(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "dismantle")

    @discord.ui.button(label="Sell", emoji="🪙", style=discord.ButtonStyle.danger, row=1)
    async def sell(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "sell")

    @discord.ui.button(label="Enchant", emoji="🔯", style=discord.ButtonStyle.primary, row=2)
    async def enchant(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "enchant")

    @discord.ui.button(label="Reroll", emoji="🎲", style=discord.ButtonStyle.secondary, row=2)
    async def reroll(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "reroll")

    @discord.ui.button(label="Identify", emoji="🔮", style=discord.ButtonStyle.success, row=2)
    async def identify(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._inventory_interaction(interaction, self.selected_id, "identify")

    @discord.ui.button(label="Return", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._adventure_embed(profile),
            view=AdventureView(self.cog, self.user_id),
        )


class RetireConfirmView(OwnedView):
    """Destructive character retirement confirmation."""

    @discord.ui.button(label="Retire Character", emoji="🪦", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        await self.cog.config.member_from_ids(interaction.guild.id, interaction.user.id).clear()
        embed = discord.Embed(
            title="🪦 The chronicle closes",
            description=(
                "Your character and all of their progress have been permanently retired.\n"
                "Use `/deepdelve create` whenever you are ready to begin a new legend."
            ),
            color=DANGER_COLOR,
        )
        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Keep Adventuring", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self.cog._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self.cog._profile_embed(interaction.user, profile),
            view=AdventureView(self.cog, self.user_id),
        )


class WorldBossView(discord.ui.View):
    """Server-wide raid control usable by every delver."""

    def __init__(self, cog: DeepDelve) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
    ) -> None:
        LOGGER.error(
            "DeepDelve world-boss callback failed for %s",
            type(item).__name__,
            exc_info=(type(error), error, error.__traceback__),
        )
        await self.cog._persistent_error(
            interaction,
            "The raid control hit an unexpected snag. Try it again in a moment.",
        )

    @discord.ui.button(
        label="Raid Strike",
        emoji="⚔️",
        style=discord.ButtonStyle.danger,
        custom_id="deepdelve:worldboss:strike",
    )
    async def strike(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog._world_boss_strike(interaction)

    @discord.ui.button(
        label="Inspect",
        emoji="🔎",
        style=discord.ButtonStyle.secondary,
        custom_id="deepdelve:worldboss:inspect",
    )
    async def inspect(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        record = await self.cog.config.guild(interaction.guild).world_boss()
        await interaction.edit_original_response(
            embed=self.cog._world_boss_embed(record),
            view=WorldBossView(self.cog),
        )


class DeepDelve(DashboardIntegration, commands.Cog):
    """An old-school persistent text RPG built for Discord."""

    __author__ = "Taako"
    __version__ = "5.0.1"

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, identifier=3847291056, force_registration=True)
        self.config.register_guild(
            enabled=True,
            adventure_channel=0,
            daily_turns=24,
            economy_mode="internal",
            parties={},
            auctions={},
            player_guilds={},
            arenas={},
            world_boss={},
            world_boss_defeated_at="",
            auction_counter=0,
            server_firsts={},
            schema_version=GUILD_SCHEMA_VERSION,
            town={
                "level": 1,
                "treasury": 0,
                "buildings": {"forge": 0, "infirmary": 0, "archive": 0, "watch": 0},
                "contributors": {},
            },
            event_announcement_channel=0,
            content_multiplier=1.0,
            season_archive=[],
            living_campaign={"act": 0, "scene": 0, "decision": 0, "choices": {}, "completed": [], "ending": ""},
            season_story={"active": "", "scene": 0},
            commissions={"week": "", "offers": [], "active": {}, "completed": 0},
            profession_mastery_points=0,
        )
        self.config.register_member(
            created=False,
            character_name="",
            class_key="",
            level=1,
            xp=0,
            gold=40,
            hp=0,
            mana=0,
            potions=2,
            floor=1,
            rooms_cleared=0,
            turns=24,
            turn_date="",
            encounter={},
            inventory=[],
            equipment={"weapon": None, "armor": None, "charm": None},
            kills=0,
            deaths=0,
            bosses=0,
            deepest_floor=1,
            achievements=[],
            discovered=[],
            status={},
            choice={},
            materials={"iron": 0, "silk": 0, "ember": 0, "essence": 0, "voidglass": 0},
            lore=[],
            journal=[],
            active_contract={},
            contracts_completed=0,
            crafted=0,
            reputation=0,
            currency_name="gold",
            background="",
            alignment="Unwritten",
            attributes={"might": 0, "finesse": 0, "insight": 0, "vitality": 0, "fortune": 0},
            attribute_points=0,
            talent_points=0,
            talents={},
            subclass="",
            skill_cooldowns={},
            combat_flags={},
            titles=[],
            current_title="",
            scars=[],
            blessings=[],
            npc_reputation={"orra": 0, "mara": 0, "vesper": 0, "rook": 0},
            story_flags=[],
            item_codex=[],
            arcane_shards=0,
            party_id="",
            party_bonus={},
            party_role="",
            player_guild_id="",
            guild_bonus={},
            arena_wins=0,
            arena_losses=0,
            prestige=0,
            ascensions=0,
            rifts_completed=0,
            hardcore=False,
            hardcore_dead=False,
            season_id="",
            season_points=0,
            daily_date="",
            daily_score=0,
            rift_state={},
            ability_casts=0,
            free_revive=True,
            pending_server_first="",
            progression_migrated=False,
            map_nodes=[],
            created_at="",
            schema_version=PROFILE_SCHEMA_VERSION,
            tutorial_step=0,
            tutorial_complete=False,
            campaign={"chapter": 0, "scene": 0, "choices": {}, "completed": [], "ending": ""},
            active_puzzle={},
            solved_puzzles=[],
            puzzle_streak=0,
            companions={},
            active_companion="",
            profession={"key": "", "level": 1, "xp": 0},
            profession_mastery={},
            event_tokens=0,
            world_events_seen=[],
            town_contribution=0,
            gather_date="",
            gather_actions=0,
            town_bonus={},
            world_event={},
            origin_complete=False,
            starter_choice="",
            stash=[],
            loadouts={},
            favorite_items=[],
            auto_dismantle=-1,
            consumables={},
            recipes=[],
            bestiary={},
            active_rumor={},
            rumors_completed=0,
            story_relics=[],
            run_history=[],
            floor_mutator={},
            boss_relic_pity=0,
            loot_pity=0,
            camp_choices=0,
            secret_rooms=0,
            morality=0,
            convictions={"mercy": 0, "honesty": 0, "ambition": 0, "ruthlessness": 0},
            moral_deeds=[],
            deed_counts={},
            conviction_fatigue=0,
            set_pity=0,
            set_discoveries={},
            set_fragments={},
            legendary_codex=[],
            legacy={
                "resolve": 0,
                "resolve_earned": 0,
                "unlocked_tenets": [],
                "active_tenets": [],
                "faction_reputation": {"lantern": 0, "concord": 0, "court": 0},
                "oath": "",
                "oath_board_date": "",
                "oath_board": [],
                "redemption": {},
                "consequence_flags": [],
                "resolve_sources": [],
                "service_dates": {},
            },
            quests_v2={
                "active": {},
                "completed": {},
                "failed": {},
                "choice_flags": [],
                "counters": {},
                "claim_tokens": [],
            },
            relationships={},
            mailbox=[],
            mail_read=[],
            nemeses={"active": [], "defeated": [], "next_id": 1},
            atlas={"discovered": [], "completed": [], "shortcuts": [], "active_dungeon": {}, "clues": {}},
            sanctum={
                "rooms": {"hall": 0, "library": 0, "workshop": 0, "garden": 0, "observatory": 0},
                "spent": 0,
                "cosmetics": [],
                "active_cosmetic": "",
            },
            season_archive=[],
        )
        self._locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._guild_locks: dict[int, asyncio.Lock] = {}
        self._currency_names: dict[int, str] = {}
        self._world_boss_view: WorldBossView | None = None

    async def cog_load(self) -> None:
        """Migrate stored data and restore server-wide persistent controls."""
        self._purge_live_player_views()
        self._world_boss_view = WorldBossView(self)
        self.bot.add_view(self._world_boss_view)
        self.bot.add_dynamic_items(DeepDelveDynamicButton, DeepDelveDynamicSelect)
        await self._migrate_all_data()

    def cog_unload(self) -> None:
        """Release per-session synchronization state."""
        self._locks.clear()
        self._guild_locks.clear()
        self._purge_live_player_views()
        if self._world_boss_view:
            self.bot.remove_view(self._world_boss_view)
            self._world_boss_view = None
        self.bot.remove_dynamic_items(DeepDelveDynamicButton, DeepDelveDynamicSelect)

    def _purge_live_player_views(self) -> None:
        """Remove legacy message-bound views so only dynamic recovery handles clicks."""
        try:
            connection = getattr(self.bot, "_connection", None)
            store = getattr(connection, "_view_store", None)
            buckets = getattr(store, "_views", {})
            if not isinstance(buckets, dict):
                return
            stale_views: dict[int, discord.ui.View] = {}
            for items in list(buckets.values()):
                if not isinstance(items, dict):
                    continue
                for item in list(items.values()):
                    custom_id = str(getattr(item, "custom_id", ""))
                    view = getattr(item, "view", None)
                    if custom_id.startswith(("deepdelve:b:", "deepdelve:s:")) and view is not None:
                        stale_views[id(view)] = view
            remove_view = getattr(self.bot, "remove_view", None)
            if not callable(remove_view):
                return
            for view in stale_views.values():
                try:
                    remove_view(view)
                except Exception:  # noqa: BLE001 - optional cross-version cleanup
                    LOGGER.debug("Could not remove one legacy DeepDelve view.", exc_info=True)
            if stale_views:
                LOGGER.info("Removed %s legacy message-bound DeepDelve view(s).", len(stale_views))
        except Exception:  # noqa: BLE001 - discord.py private internals vary
            # This cleanup uses discord.py's private view-store shape and must remain
            # optional when Red ships a different compatible library version.
            LOGGER.warning("Skipped legacy DeepDelve view cleanup for this runtime.", exc_info=True)

    async def _migrate_all_data(self) -> None:
        """Run idempotent schema upgrades for every stored guild and character."""
        all_guilds = await self.config.all_guilds()
        for guild_id, guild_data in all_guilds.items():
            if migrate_guild(guild_data):
                await self.config.guild_from_id(int(guild_id)).set(guild_data)
        all_members = await self.config.all_members()
        for guild_id, members in all_members.items():
            for user_id, profile in members.items():
                if migrate_profile(profile):
                    await self.config.member_from_ids(int(guild_id), int(user_id)).set(profile)

    def _lock_for(self, guild_id: int, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault((guild_id, user_id), asyncio.Lock())

    def _guild_lock_for(self, guild_id: int) -> asyncio.Lock:
        return self._guild_locks.setdefault(guild_id, asyncio.Lock())

    @classmethod
    def _safe_config_merge(cls, defaults: Any, current: Any) -> Any:
        """Overlay raw Config data without recursing into ``None`` defaults."""
        if not isinstance(current, Mapping):
            return copy.deepcopy(current)
        result = copy.deepcopy(defaults) if isinstance(defaults, Mapping) else {}
        for key, value in current.items():
            if isinstance(value, Mapping):
                result[key] = cls._safe_config_merge(result.get(key, {}), value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    async def _raw_member_profile(self, guild_id: int, user_id: int) -> tuple[Any, dict[str, Any]]:
        """Read member data without Red's unsafe nested ``None`` merge."""
        proxy = self.config.member_from_ids(guild_id, user_id)
        raw = await proxy.get_raw(default=None)
        profile = self._safe_config_merge(proxy.defaults, raw or {})
        return proxy, profile

    @staticmethod
    async def _persistent_error(interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _hub_interaction(self, interaction: discord.Interaction, screen: str) -> None:
        """Open a current-state hub screen while acknowledging Discord immediately."""
        if not interaction.guild:
            await self._persistent_error(interaction, "DeepDelve controls can only be used inside a server.")
            return
        if screen == "inventory":
            await self._show_inventory_interaction(interaction)
            return
        await interaction.response.defer()
        profile = await self._get_profile(interaction.guild.id, interaction.user.id)
        if not profile.get("created"):
            await interaction.edit_original_response(embed=self._not_created_embed(), view=None)
            return
        if screen == "resume":
            if profile.get("encounter"):
                embed = self._combat_embed(profile, "Your unfinished battle resumes.")
                view: discord.ui.View = CombatView(self, interaction.user.id, profile)
            elif profile.get("choice"):
                embed = self._choice_embed(profile)
                view = ChoiceView(self, interaction.user.id, profile["choice"])
            elif profile.get("active_puzzle"):
                embed = self._puzzle_embed(profile)
                view = PuzzleView(self, interaction.user.id, profile["active_puzzle"])
            else:
                embed = self._adventure_embed(profile)
                view = AdventureView(self, interaction.user.id)
        elif screen == "quests":
            embed, view = self._quest_journal_embed(profile), QuestJournalView(self, interaction.user.id, profile)
        elif screen == "atlas":
            embed, view = self._atlas_embed(profile), AtlasView(self, interaction.user.id, profile)
        elif screen == "character":
            embed, view = self._profile_embed(interaction.user, profile), GameHubView(self, interaction.user.id)
        elif screen == "morality":
            embed, view = self._morality_embed(profile), GameHubView(self, interaction.user.id)
        elif screen == "codex":
            embed, view = self._collection_codex_embed(profile), GameHubView(self, interaction.user.id)
        elif screen == "town":
            embed, view = self._town_embed(profile), TownView(self, interaction.user.id)
        elif screen == "mail":
            starting_gold = profile["gold"]
            generate_mail(profile)
            await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
            embed, view = self._mail_embed(profile), GameHubView(self, interaction.user.id)
        elif screen == "sanctum":
            embed, view = self._sanctum_embed(profile), GameHubView(self, interaction.user.id)
        elif screen == "activities":
            embed, view = self._activities_embed(profile), ActivitiesView(self, interaction.user.id)
        elif screen == "profession":
            embed, view = self._profession_embed(profile), ProfessionView(self, interaction.user.id, profile)
        elif screen == "companions":
            embed, view = self._companion_embed(profile), CompanionView(self, interaction.user.id, profile)
        elif screen == "commissions":
            starting_gold = profile["gold"]
            embed = self._commissions_embed(profile)
            await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
            view = CommissionsView(self, interaction.user.id, profile)
        elif screen == "saga":
            embed, view = self._living_campaign_embed(profile), SagaView(self, interaction.user.id, profile)
        elif screen == "archive":
            embed, view = self._season_archive_embed(profile), SeasonArchiveView(self, interaction.user.id, profile)
        else:
            embed, view = self._game_hub_embed(profile), GameHubView(self, interaction.user.id)
        await interaction.edit_original_response(embed=embed, view=view)

    async def _dispatch_persistent_button(self, interaction: discord.Interaction, route: str) -> None:
        """Dispatch a player control reconstructed after a restart."""
        if not interaction.guild:
            await self._persistent_error(interaction, "DeepDelve controls can only be used inside a server.")
            return
        user_id = interaction.user.id
        if route == "adventure:explore":
            await self._handle_explore_interaction(interaction)
        elif route == "adventure:character":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._profile_embed(interaction.user, profile),
                view=AdventureView(self, user_id),
            )
        elif route.startswith("gamehub:"):
            await self._hub_interaction(interaction, route.partition(":")[2])
        elif route == "adventure:inventory":
            await self._show_inventory_interaction(interaction)
        elif route == "adventure:town":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._town_embed(profile),
                view=TownView(self, user_id),
            )
        elif route == "adventure:game_hub":
            await self._hub_interaction(interaction, "hub")
        elif route in {"combat:attack", "combat:defend", "combat:potion", "combat:flee", "combat:conviction"}:
            await self._combat_interaction(interaction, route.partition(":")[2])
        elif route in {"town:rest", "town:potion", "town:meditate"}:
            await self._town_interaction(interaction, route.partition(":")[2])
        elif route == "town:contract":
            await self._contract_interaction(interaction)
        elif route == "town:forge":
            await self._show_crafting_interaction(interaction)
        elif route == "town:profession":
            await self._hub_interaction(interaction, "profession")
        elif route == "town:back":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile),
                view=AdventureView(self, user_id),
            )
        elif route.startswith("choice:"):
            await self._choice_interaction(interaction, route.partition(":")[2])
        elif route.startswith("puzzle:"):
            await self._puzzle_interaction(interaction, route.partition(":")[2])
        elif route.startswith("campaign:"):
            await self._campaign_interaction(interaction, route.partition(":")[2])
        elif route == "campaigncontinue:continue_story":
            await self._campaign_interaction(interaction, None)
        elif route in {"craft:weapon", "craft:armor", "craft:charm"}:
            await self._craft_interaction(interaction, route.partition(":")[2])
        elif route == "craft:back":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._town_embed(profile),
                view=TownView(self, user_id),
            )
        elif route.startswith("inventory:") and route.split(":", maxsplit=2)[1] in {
            "equip",
            "upgrade",
            "dismantle",
            "sell",
            "enchant",
            "reroll",
            "identify",
        }:
            route_parts = route.split(":", maxsplit=2)
            selected_id = route_parts[2] if len(route_parts) == 3 else None
            await self._inventory_interaction(interaction, selected_id, route_parts[1])
        elif route == "inventory:back":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile),
                view=AdventureView(self, user_id),
            )
        elif route == "retireconfirm:confirm":
            await interaction.response.defer()
            await self.config.member_from_ids(interaction.guild.id, user_id).clear()
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="🪦 The chronicle closes",
                    description=(
                        "Your character and all of their progress have been permanently retired.\n"
                        "Use `/deepdelve create` whenever you are ready to begin a new legend."
                    ),
                    color=DANGER_COLOR,
                ),
                view=None,
            )
        elif route == "retireconfirm:cancel":
            await interaction.response.defer()
            profile = await self._get_profile(interaction.guild.id, user_id)
            await interaction.edit_original_response(
                embed=self._profile_embed(interaction.user, profile),
                view=AdventureView(self, user_id),
            )
        elif route == "origin:begin":
            await self._origin_begin(interaction)
        elif route.startswith("activities:"):
            await self._hub_interaction(interaction, route.partition(":")[2])
        elif route == "profession:gather":
            await self._profession_gather_interaction(interaction)
        elif route == "profession:commissions":
            await self._hub_interaction(interaction, "commissions")
        elif route in {"profession:back", "companion:back"}:
            await self._hub_interaction(interaction, "activities")
        elif route == "commissions:profession":
            await self._hub_interaction(interaction, "profession")
        elif route == "commissions:back":
            await self._hub_interaction(interaction, "activities")
        elif route == "questjournal:back":
            await self._hub_interaction(interaction, "hub")
        elif route.startswith("atlas:"):
            action = route.partition(":")[2]
            if action in {"advance", "abandon"}:
                await self._atlas_menu_interaction(interaction, action, "")
            elif action == "resume":
                await self._hub_interaction(interaction, "resume")
            else:
                await self._hub_interaction(interaction, "hub")
        elif route.startswith("saga:"):
            action = route.partition(":")[2]
            if action == "back":
                await self._hub_interaction(interaction, "activities")
            else:
                choice = "" if action == "continue_story" else action
                await self._saga_menu_interaction(interaction, choice)
        elif route == "seasonarchive:advance":
            await self._archive_menu_interaction(interaction, "advance", 0)
        elif route == "seasonarchive:back":
            await self._hub_interaction(interaction, "activities")
        else:
            await self._persistent_error(
                interaction,
                "That control belongs to an older DeepDelve screen. Reopen `/deepdelve adventure`.",
            )

    async def _dispatch_persistent_select(
        self,
        interaction: discord.Interaction,
        route: str,
        values: list[str],
    ) -> None:
        """Dispatch a selector reconstructed after a restart."""
        if not interaction.guild or not values:
            await self._persistent_error(interaction, "Reopen this DeepDelve screen and try again.")
            return
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        selected = values[0]
        if route == "ability_select":
            await self._combat_interaction(interaction, f"ability:{selected}")
        elif route == "consumable_select":
            await self._combat_interaction(interaction, f"consumable:{selected}")
        elif route == "inventory_select":
            await interaction.response.defer()
            profile = await self._get_profile(guild_id, user_id)
            view = InventoryView(self, user_id, profile)
            view.bind_selection(selected)
            await interaction.edit_original_response(
                embed=self._inventory_embed(profile, selected),
                view=view,
            )
        elif route == "class_select":
            await interaction.response.defer()
            created = await self._create_character(
                guild_id,
                user_id,
                interaction.user.display_name,
                selected,
            )
            if not created:
                await interaction.followup.send(
                    "You already have a character. Use `/deepdelve retire` before starting over.",
                    ephemeral=True,
                )
                return
            profile = await self._get_profile(guild_id, user_id)
            await interaction.edit_original_response(
                embed=self._origin_embed(profile),
                view=OriginView(self, user_id, profile),
            )
        elif route in {"origin_background", "origin_starter", "origin_alignment"}:
            await self._origin_interaction(
                interaction,
                route.removeprefix("origin_"),
                selected,
            )
        elif route == "profession_select":
            await self._profession_select_interaction(interaction, selected)
        elif route == "companion_select":
            await self._companion_select_interaction(interaction, selected)
        elif route == "commission_select":
            await self._commission_select_interaction(interaction, int(selected))
        elif route == "quest_action_select":
            parts = selected.split("|", maxsplit=2)
            await self._quest_menu_interaction(
                interaction,
                parts[0],
                parts[1],
                parts[2] if len(parts) > 2 else "",
            )
        elif route == "atlas_action_select":
            action, value = selected.split("|", maxsplit=1)
            await self._atlas_menu_interaction(interaction, action, value)
        elif route == "archive_chapter_select":
            await self._archive_menu_interaction(interaction, "begin", int(selected))
        else:
            await self._persistent_error(
                interaction,
                "That selector belongs to an older DeepDelve screen. Reopen the current menu.",
            )

    async def _sync_party_bonuses(self, guild_id: int, member_ids: list[int]) -> None:
        bonus = party_bonus(len(member_ids))
        for member_id in member_ids:
            proxy, profile = await self._raw_member_profile(guild_id, member_id)
            if profile.get("created"):
                profile["party_bonus"] = bonus
                await proxy.set(profile)

    async def _sync_player_guild_bonuses(
        self,
        guild_id: int,
        member_ids: list[int],
        level: int,
    ) -> None:
        bonus = {
            "currency_percent": 2 if level >= 2 else 0,
            "luck": 2 if level >= 3 else 0,
            "daily_turns": 1 if level >= 4 else 0,
            "worldboss_percent": 5 if level >= 5 else 0,
        }
        for member_id in member_ids:
            proxy, profile = await self._raw_member_profile(guild_id, member_id)
            if profile.get("created"):
                profile["guild_bonus"] = bonus
                await proxy.set(profile)

    async def _get_profile(self, guild_id: int, user_id: int, *, refresh: bool = True) -> dict[str, Any]:
        proxy, profile = await self._raw_member_profile(guild_id, user_id)
        dirty = migrate_profile(profile)
        guild_proxy = self.config.guild_from_id(guild_id)
        guild_data = await guild_proxy.all()
        if migrate_guild(guild_data):
            await guild_proxy.set(guild_data)
        profile["town_bonus"] = town_bonuses(guild_data["town"])
        profile["world_event"] = active_world_event(guild_id)
        guild = self.bot.get_guild(guild_id)
        economy_mode = guild_data["economy_mode"]
        if economy_mode == "bank" and guild:
            member = guild.get_member(user_id)
            if member:
                profile["gold"] = await bank.get_balance(member)
                currency_name = await bank.get_currency_name(guild)
                profile["currency_name"] = currency_name
                self._currency_names[guild_id] = currency_name
        else:
            profile["currency_name"] = "gold"
        if refresh and profile["created"]:
            if not profile.get("progression_migrated"):
                profile["attribute_points"] += 5 + max(0, profile["level"] - 1) * 2
                profile["talent_points"] += 1 + max(0, profile["level"] - 1) // 2
                profile["progression_migrated"] = True
                dirty = True
            season = current_season()
            if profile.get("season_id") != season["id"]:
                profile["season_id"] = season["id"]
                profile["season_points"] = 0
                dirty = True
            today = datetime.now(timezone.utc).date().isoformat()
            if profile.get("turn_date") != today:
                daily_turns = int(guild_data["daily_turns"])
                profile["turns"] = (
                    daily_turns
                    + int(
                        profile.get("guild_bonus", {}).get("daily_turns", 0),
                    )
                    + int(profile["town_bonus"].get("daily_turns", 0))
                )
                profile["turn_date"] = today
                dirty = True
            unlocked = unlock_companions(profile)
            if unlocked:
                dirty = True
            if dirty:
                await proxy.set(profile)
        elif dirty:
            await proxy.set(profile)
        return profile

    async def _save_profile(
        self,
        guild_id: int,
        user_id: int,
        profile: dict[str, Any],
        starting_gold: int,
    ) -> dict[str, Any]:
        """Persist a profile and apply its gold delta to Red's bank when enabled."""
        refresh_titles(profile)
        economy_mode = await self.config.guild_from_id(guild_id).economy_mode()
        if economy_mode == "bank":
            guild = self.bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            if member:
                current = await bank.get_balance(member)
                desired = max(0, current + int(profile["gold"]) - int(starting_gold))
                maximum = await bank.get_max_balance(guild)
                profile["gold"] = await bank.set_balance(member, min(desired, maximum))
                self._currency_names[guild_id] = await bank.get_currency_name(guild)
        await self.config.member_from_ids(guild_id, user_id).set(profile)
        return profile

    def _currency(self, guild_id: int | None = None) -> str:
        if guild_id is None:
            return "gold"
        return self._currency_names.get(guild_id, "gold")

    async def _send_art_embed(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        asset_name: str,
        *,
        view: discord.ui.View | None = None,
    ) -> None:
        """Send an embed with a bundled art asset when available."""
        asset_path = Path(__file__).parent / "assets" / asset_name
        if asset_path.is_file():
            embed.set_image(url=f"attachment://{asset_name}")
            await ctx.send(
                embed=embed,
                view=view,
                file=discord.File(asset_path, filename=asset_name),
            )
            return
        await ctx.send(embed=embed, view=view)

    @staticmethod
    def _money(profile: dict[str, Any], amount: int | None = None) -> str:
        currency = profile.get("currency_name", "gold")
        return currency if amount is None else f"{amount} {currency}"

    async def _create_character(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        class_key: str,
    ) -> bool:
        async with self._lock_for(guild_id, user_id):
            proxy, current = await self._raw_member_profile(guild_id, user_id)
            if current["created"] or class_key not in GAME_CLASSES:
                return False
            details = GAME_CLASSES[class_key]
            daily_turns = await self.config.guild_from_id(guild_id).daily_turns()
            current.update(
                {
                    "created": True,
                    "character_name": display_name[:32],
                    "class_key": class_key,
                    "hp": details["max_hp"],
                    "mana": details["max_mana"],
                    "turns": daily_turns,
                    "turn_date": datetime.now(timezone.utc).date().isoformat(),
                    "attribute_points": 5,
                    "talent_points": 1,
                    "titles": ["delver"],
                    "current_title": "delver",
                    "progression_migrated": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await proxy.set(current)
            return True

    @staticmethod
    def _origin_embed(profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        """Render the character-origin sequence."""
        class_details = GAME_CLASSES[profile["class_key"]]
        background = BACKGROUNDS.get(profile.get("background", ""))
        starter = starter_options(profile["class_key"]).get(profile.get("starter_choice", ""))
        alignment = profile.get("alignment", "Unwritten")
        complete = bool(background and starter and alignment != "Unwritten")
        embed = discord.Embed(
            title="🕯️ Write Your Origin",
            description=(
                (f"{narrative}\n\n" if narrative else "")
                + f"{class_details['emoji']} **{profile['character_name']} — {class_details['name']}**\n"
                "These choices define your opening tools and story checks. They remain changeable until you begin."
            ),
            color=SUCCESS_COLOR if complete else EMBED_COLOR,
        )
        embed.add_field(
            name="1. Background",
            value=(
                f"{background['emoji']} **{background['name']}**\n{background['description']}" if background else "Not chosen"
            ),
            inline=False,
        )
        embed.add_field(
            name="2. Origin Weapon",
            value=(f"{starter['emoji']} **{starter['name']}**\n{starter['description']}" if starter else "Not chosen"),
            inline=False,
        )
        embed.add_field(
            name="3. Alignment",
            value=(
                f"**{alignment}** — begins at {origin_morality(alignment):+d} Morality; your deeds decide what follows."
                if alignment != "Unwritten"
                else "Not chosen"
            ),
            inline=False,
        )
        embed.set_footer(
            text=(
                "All origin choices are ready. Begin the descent." if complete else "Choose all three entries before beginning."
            ),
        )
        return embed

    async def _origin_interaction(
        self,
        interaction: discord.Interaction,
        field: str,
        value: str,
    ) -> None:
        """Persist one reversible origin choice."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if profile.get("origin_complete"):
                await interaction.followup.send("Your origin is already written.", ephemeral=True)
                return
            narrative = ""
            if field == "background" and value in BACKGROUNDS:
                details = BACKGROUNDS[value]
                profile["background"] = value
                narrative = f"{details['emoji']} Your history becomes **{details['name']}**."
            elif field == "starter" and value in starter_options(profile["class_key"]):
                profile["starter_choice"] = value
                narrative = f"⚔️ You claim **{starter_options(profile['class_key'])[value]['name']}**."
            elif field == "alignment" and value in {"Radiant", "Pragmatic", "Umbral"}:
                profile["alignment"] = value
                narrative = f"⚖️ Your chronicle bends toward **{value}**."
            else:
                await interaction.followup.send("That origin choice is not available.", ephemeral=True)
                return
            await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        await interaction.edit_original_response(
            embed=self._origin_embed(profile, narrative),
            view=OriginView(self, interaction.user.id, profile),
        )

    async def _origin_begin(self, interaction: discord.Interaction) -> None:
        """Finalize origin choices and equip the selected starter weapon."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            ready = profile.get("background") and profile.get("starter_choice") and profile.get("alignment") != "Unwritten"
            if not ready:
                await interaction.followup.send("Choose a background, weapon, and alignment first.", ephemeral=True)
                return
            if not profile.get("origin_complete"):
                background = BACKGROUNDS[profile["background"]]
                for attribute, amount in background["attributes"].items():
                    profile["attributes"][attribute] += amount
                profile["gold"] += background["gold"]
                profile["potions"] += background["potions"]
                profile["morality"] = origin_morality(profile["alignment"])
                starter = create_starter_item(profile["class_key"], profile["starter_choice"])
                profile["equipment"]["weapon"] = starter
                self._record_item(profile, starter)
                profile["origin_complete"] = True
                profile["hp"] = self._stats(profile)["max_hp"]
                profile["mana"] = self._stats(profile)["max_mana"]
                self._journal(profile, f"Claimed the origin weapon {starter['name']}.")
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        await interaction.edit_original_response(
            embed=self._adventure_embed(
                profile,
                "🕯️ **Your origin is written.** The first stair opens beneath Lastlight.",
            ),
            view=AdventureView(self, interaction.user.id),
        )

    @staticmethod
    def _equipment_totals(profile: dict[str, Any]) -> dict[str, int]:
        totals = {"attack": 0, "defense": 0, "hp": 0, "luck": 0}
        for item in profile.get("equipment", {}).values():
            if not item:
                continue
            for stat in totals:
                totals[stat] += int(item.get(stat, 0))
        return totals

    def _stats(self, profile: dict[str, Any]) -> dict[str, int]:
        details = GAME_CLASSES[profile["class_key"]]
        level = int(profile["level"])
        gear = self._equipment_totals(profile)
        set_bonuses, _effects = equipment_set_bonuses(profile.get("equipment", {}))
        progression = progression_bonuses(profile)
        companion = companion_bonuses(profile)
        story = campaign_bonuses(profile)
        stats = {
            "max_hp": details["max_hp"] + (level - 1) * 7 + gear["hp"],
            "max_mana": details["max_mana"] + (level - 1) * 3,
            "attack": details["attack"]
            + round((level - 1) * (1.6 if profile["class_key"] == "vanguard" else 2))
            + gear["attack"],
            "defense": details["defense"] + (level - 1) + gear["defense"],
            "luck": details["luck"] + (level - 1) // 3 + gear["luck"],
        }
        for stat in ("attack", "defense", "luck"):
            stats[stat] += set_bonuses.get(stat, 0) + progression.get(stat, 0) + companion.get(stat, 0) + story.get(stat, 0)
        stats["max_hp"] += set_bonuses.get("hp", 0) + progression.get("hp", 0) + story.get("hp", 0)
        stats["max_mana"] += set_bonuses.get("mana", 0) + progression.get("mana", 0) + story.get("mana", 0)
        stats["max_hp"] = round(stats["max_hp"] * (1 + progression.get("hp_percent", 0) / 100))
        stats["max_mana"] = round(
            stats["max_mana"] * (1 + progression.get("mana_percent", 0) / 100),
        )
        stats["attack"] = round(
            stats["attack"] * (1 + progression.get("attack_percent", 0) / 100),
        )
        stats["critical_bonus"] = progression.get("critical", 0)
        stats["ability_percent"] = progression.get("ability_percent", 0)
        subclass = profile.get("subclass")
        if subclass == "berserker" and profile.get("hp", stats["max_hp"]) <= stats["max_hp"] // 2:
            stats["attack"] = round(stats["attack"] * 1.25)
        elif subclass == "trickster":
            stats["luck"] += 5
            stats["critical_bonus"] += 5
        elif subclass == "warlord":
            stats["attack"] += 2
            stats["defense"] += 2
        equipped_effects = equipment_effects(profile.get("equipment", {}))
        set_counts: dict[str, int] = {}
        for item in profile.get("equipment", {}).values():
            if item and item.get("set"):
                set_counts[item["set"]] = set_counts.get(item["set"], 0) + 1
        if "crown" in equipped_effects:
            condition_count = len(profile.get("status", {}))
            stats["attack"] += condition_count * 3
            stats["defense"] += condition_count * 2
        if "origin_knives" in equipped_effects:
            stats["critical_bonus"] += 4
        if profile.get("status", {}).get("curse") and ("eclipse" in equipped_effects or "defiance" in equipped_effects):
            stats["attack"] = round(stats["attack"] * 1.15)
        if set_counts.get("bloodforged", 0) >= 3 and profile.get("hp", stats["max_hp"]) <= stats["max_hp"] // 2:
            stats["critical_bonus"] += 8
        stats["attack"] += int(profile.get("combat_flags", {}).get("consumable_attack", 0))
        stats["luck"] += int(profile.get("combat_flags", {}).get("consumable_luck", 0))
        return stats

    def _generate_item(
        self,
        profile: dict[str, Any],
        floor: int,
        luck: int,
        *,
        slot: str | None = None,
    ) -> dict[str, Any]:
        forced_set = ""
        if int(profile.get("set_pity", 0)) >= 5:
            eligible = [
                (key, details)
                for key, details in ITEM_SETS.items()
                if profile["class_key"] in details["classes"]
                and (
                    not details.get("subclasses")
                    or profile.get("subclass", "") in details["subclasses"]
                )
            ]
            subclass_sets = [
                entry
                for entry in eligible
                if entry[1].get("subclasses")
            ]
            candidates = subclass_sets or eligible
            if candidates:
                forced_set, _details = random.choice(candidates)
                discovered = set(profile.get("set_discoveries", {}).get(forced_set, []))
                missing = [candidate for candidate in ("weapon", "armor", "charm") if candidate not in discovered]
                if missing:
                    slot = random.choice(missing)
        item = generate_item(
            floor,
            luck,
            slot=slot,
            rarity_index=3 if forced_set else None,
        )
        item = apply_advanced_itemization(
            item,
            floor,
            profile["class_key"],
            profile.get("subclass", ""),
        )
        if forced_set:
            item["set"] = forced_set
            item["legendary"] = False
            item["bound"] = False
            details = ITEM_SETS[forced_set]
            item["name"] = f"{details['name']} {item['name'].split()[-1]}"
            item["codex_key"] = item["name"].lower().replace(" ", "_")
            item["set_pity_drop"] = True
        self._record_item(profile, item)
        return item

    @staticmethod
    def _apply_challenge_enemy_modifier(
        enemy: dict[str, Any],
        challenge_name: str,
        rng: random.Random = random,
    ) -> dict[str, Any]:
        if "Blood Moon" in challenge_name:
            enemy["attack"] = round(enemy["attack"] * 1.25)
        elif "Glass Labyrinth" in challenge_name:
            enemy["attack"] = round(enemy["attack"] * 1.4)
        elif "Royal Hunt" in challenge_name and not enemy.get("affix"):
            affix = dict(rng.choice(AFFIXES))
            enemy["name"] = f"{affix['name']} {enemy['name']}"
            enemy["emoji"] = affix["emoji"]
            for field in ("hp", "attack", "defense"):
                floor = int(enemy.get("floor", 1))
                endurance = max(1.25, 1.5 - max(0, floor - 1) * 0.01) if field == "hp" else 1.0
                enemy[field] = max(1, round(enemy[field] * affix[field] * endurance))
            enemy["max_hp"] = enemy["hp"]
            enemy["gold"] = round(enemy["gold"] * 1.5)
            enemy["xp"] = round(enemy["xp"] * 1.4)
            enemy["affix"] = affix
        return enemy

    @staticmethod
    def _force_affix(enemy: dict[str, Any], rng: random.Random = random) -> dict[str, Any]:
        """Promote an enemy to elite for authored events."""
        if enemy.get("boss") or enemy.get("affix"):
            return enemy
        affix = dict(rng.choice(AFFIXES))
        enemy["name"] = f"{affix['name']} {enemy['name']}"
        enemy["emoji"] = affix["emoji"]
        for field in ("hp", "attack", "defense"):
            floor = int(enemy.get("floor", 1))
            endurance = max(1.25, 1.5 - max(0, floor - 1) * 0.01) if field == "hp" else 1.0
            enemy[field] = max(1, round(enemy[field] * affix[field] * endurance))
        enemy["max_hp"] = enemy["hp"]
        enemy["gold"] = round(enemy["gold"] * 1.5)
        enemy["xp"] = round(enemy["xp"] * 1.4)
        enemy["affix"] = affix
        return enemy

    @staticmethod
    def _record_item(profile: dict[str, Any], item: dict[str, Any]) -> None:
        if not item.get("identified", True):
            return
        key = item.get("codex_key", item["name"].lower().replace(" ", "_"))
        codex = profile.setdefault("item_codex", [])
        if key not in codex:
            codex.append(key)
        if item.get("legendary") and item["name"] not in profile.setdefault("legendary_codex", []):
            profile["legendary_codex"].append(item["name"])

    @staticmethod
    def _record_set_discovery(profile: dict[str, Any], item: dict[str, Any]) -> None:
        """Permanently record a newly acquired set slot."""
        set_key = item.get("set", "")
        slot = item.get("slot", "")
        if not set_key or slot not in {"weapon", "armor", "charm"}:
            return
        discoveries = profile.setdefault("set_discoveries", {}).setdefault(set_key, [])
        if slot not in discoveries:
            discoveries.append(slot)

    def _store_loot(self, profile: dict[str, Any], item: dict[str, Any]) -> str:
        """Store, auto-dismantle, or convert one drop with comparison context."""
        self._record_item(profile, item)
        rarity = RARITIES[int(item.get("rarity_index", 0))]
        set_key = item.get("set", "")
        if set_key:
            profile["set_pity"] = 0
            owned_matches = [
                owned
                for owned in [
                    *profile.get("inventory", []),
                    *profile.get("stash", []),
                    *(equipped for equipped in profile.get("equipment", {}).values() if equipped),
                ]
                if owned.get("set") == set_key and owned.get("slot") == item.get("slot")
            ]
            if owned_matches and item_power(item) <= max(item_power(owned) for owned in owned_matches):
                profile.setdefault("set_fragments", {})[set_key] = (
                    int(profile.get("set_fragments", {}).get(set_key, 0)) + 1
                )
                profile["arcane_shards"] += 2
                return (
                    f"🧩 Duplicate **{ITEM_SETS[set_key]['name']} {item['slot']}** converted into "
                    "**1 set fragment** and **2 arcane shards**."
                )
            self._record_set_discovery(profile, item)
        elif int(item.get("rarity_index", 0)) >= 2:
            profile["set_pity"] = min(5, int(profile.get("set_pity", 0)) + 1)
        if should_auto_dismantle(profile, item):
            currency, shards = dismantle_rewards(item)
            profile["gold"] += currency
            profile["arcane_shards"] += shards
            return (
                f"🔨 Auto-dismantled {rarity['emoji']} **{item['name']}** into "
                f"**{shards} shards** and **{self._money(profile, currency)}**."
            )
        if len(profile["inventory"]) >= 25:
            bonus = 15 + profile["floor"] * 2
            profile["gold"] += bonus
            return f"🎒 Pack full: **{item['name']}** is exchanged for **{self._money(profile, bonus)}**."
        profile["inventory"].append(item)
        equipped = profile["equipment"].get(item["slot"])
        source = f" • {item.get('source')}" if item.get("source") else ""
        return (
            f"{rarity['emoji']} **{item['rarity'].upper()} RELIC:** {item['name']}{source}\n"
            f"{item_stat_line(item)}\n{comparison_line(item, equipped)}"
        )

    @staticmethod
    def _class_details(profile: dict[str, Any]) -> dict[str, Any]:
        return GAME_CLASSES[profile["class_key"]]

    def _profile_embed(self, user: discord.abc.User, profile: dict[str, Any]) -> discord.Embed:
        if not profile.get("created"):
            return self._not_created_embed()
        details = self._class_details(profile)
        stats = self._stats(profile)
        xp_needed = xp_for_level(profile["level"])
        title_text = ""
        if profile.get("current_title"):
            title_key = profile["current_title"]
            title_text = f" • {TITLES.get(title_key, (title_key, ''))[0]}"
        subclass = SUBCLASSES.get(profile["class_key"], {}).get(profile.get("subclass", ""))
        class_name = subclass["name"] if subclass else details["name"]
        moral = morality_path(profile)
        moral_score = int(profile.get("morality", 0))
        convictions = profile.get("convictions", {})
        embed = discord.Embed(
            title=(
                f"{moral['emoji']} {details['emoji']} {profile['character_name']} — "
                f"Level {profile['level']} {class_name}{title_text}"
            ),
            description=f"{details['description']}\n\n*{moral['appearance']}*",
            color=moral["color"],
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(
            name="Vitality",
            value=(
                f"❤️ `{profile['hp']}/{stats['max_hp']}` {progress_bar(profile['hp'], stats['max_hp'])}\n"
                f"🔷 `{profile['mana']}/{stats['max_mana']}` {progress_bar(profile['mana'], stats['max_mana'])}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Attributes",
            value=(f"⚔️ **{stats['attack']}** ATK\n🛡️ **{stats['defense']}** DEF\n🍀 **{stats['luck']}** LUCK"),
        )
        embed.add_field(
            name="Progress",
            value=(
                f"✨ `{profile['xp']}/{xp_needed}` XP\n"
                f"🏰 Floor **{profile['floor']}** · Room **{profile['rooms_cleared'] + 1}/5**\n"
                f"🧭 **{profile['turns']}** turns\n"
                f"🤝 **{profile.get('reputation', 0)}** Lastlight reputation"
            ),
        )
        equip_lines = []
        for slot, emoji in (("weapon", "⚔️"), ("armor", "🛡️"), ("charm", "📿")):
            item = profile["equipment"].get(slot)
            equip_lines.append(f"{emoji} **{slot.title()}:** {item['name'] if item else 'Empty'}")
        embed.add_field(name="Equipment", value="\n".join(equip_lines), inline=False)
        embed.add_field(
            name=f"{moral['emoji']} Morality — {moral['name']} ({moral_score:+d})",
            value=(
                f"🌑 {progress_bar(moral_score + 100, 200, 12)} ☀️\n"
                f"🤍 Mercy **{convictions.get('mercy', 0)}** • "
                f"👁️ Honesty **{convictions.get('honesty', 0)}**\n"
                f"🔥 Ambition **{convictions.get('ambition', 0)}** • "
                f"🗡️ Ruthlessness **{convictions.get('ruthlessness', 0)}**"
            ),
            inline=False,
        )
        attributes = profile.get("attributes", {})
        embed.add_field(
            name="Build",
            value=(
                f"💪 MGT {attributes.get('might', 0)} • "
                f"🦶 FIN {attributes.get('finesse', 0)} • "
                f"🧠 INS {attributes.get('insight', 0)}\n"
                f"❤️ VIT {attributes.get('vitality', 0)} • "
                f"🎲 FOR {attributes.get('fortune', 0)}\n"
                f"**{profile.get('attribute_points', 0)} attribute** and "
                f"**{profile.get('talent_points', 0)} talent points** available"
            ),
            inline=False,
        )
        if profile.get("scars") or profile.get("blessings"):
            embed.add_field(
                name="Marks of the Journey",
                value=(
                    f"🩸 **Scars:** {humanize_list(profile['scars']) if profile['scars'] else 'None'}\n"
                    f"✨ **Blessings:** "
                    f"{humanize_list(profile['blessings']) if profile['blessings'] else 'None'}"
                ),
                inline=False,
            )
        if not profile.get("tutorial_complete"):
            embed.add_field(
                name="🕯️ New Delver Guidance",
                value=(
                    "Open `/deepdelve chronicle tutorial` for the five-part Delver's Primer, "
                    "then begin with `/deepdelve adventure`."
                ),
                inline=False,
            )
        embed.set_footer(
            text=(
                f"🪙 {self._money(profile, profile['gold'])}  •  🧪 {profile['potions']} potions  •  "
                f"☠️ {profile['kills']} kills  •  🏆 {profile['bosses']} bosses"
            ),
        )
        return embed

    def _game_hub_embed(self, profile: dict[str, Any]) -> discord.Embed:
        """Render the persistent browser-RPG dashboard."""
        moral = morality_path(profile)
        legacy = ensure_legacy(profile)
        quests = profile.get("quests_v2", {})
        active = quests.get("active", {})
        ready = sum(int(value.get("progress", 0)) >= int(value.get("target", 1)) for value in active.values())
        unread = len([letter for letter in profile.get("mailbox", []) if letter["key"] not in profile.get("mail_read", [])])
        nemeses = ensure_nemeses(profile)
        atlas = profile.get("atlas", {})
        current_objective = "No active quests"
        if active:
            key, progress = next(iter(active.items()))
            definition = QUESTS.get(key, {"name": key})
            current_objective = f"**{definition['name']}** — {progress['progress']}/{progress['target']}"
        embed = discord.Embed(
            title=f"🕯️ DeepDelve 5.0 — {profile['character_name']}",
            description=(
                f"*{moral['appearance']}*\n\n"
                f"**Current Objective**\n{current_objective}"
            ),
            color=moral["color"],
        )
        embed.add_field(
            name="Expedition",
            value=(
                f"🏰 Floor **{profile['floor']}** • deepest **{profile['deepest_floor']}**\n"
                f"🧭 Energy **{profile['turns']}** • room **{profile['rooms_cleared'] + 1}/5**\n"
                f"❤️ {profile['hp']} health • 🔷 {profile['mana']} mana"
            ),
        )
        embed.add_field(
            name="Living World",
            value=(
                f"📜 **{len(active)}** active • **{ready}** ready\n"
                f"✉️ **{unread}** unread letters\n"
                f"👁️ **{len(nemeses['active'])}** Nemeses hunting"
            ),
        )
        embed.add_field(
            name=f"{moral['emoji']} Legacy",
            value=(
                f"**{moral['name']}** ({int(profile.get('morality', 0)):+d})\n"
                f"◆ **{legacy['resolve']}** Resolve\n"
                f"📜 **{len(legacy['active_tenets'])}/3** active Tenets"
            ),
        )
        embed.add_field(
            name="Factions",
            value="\n".join(
                f"{FACTIONS[key]['emoji']} {FACTIONS[key]['name']}: **{legacy['faction_reputation'][key]}**"
                for key in FACTIONS
            ),
            inline=False,
        )
        embed.add_field(
            name="World Progress",
            value=(
                f"🗺️ **{len(atlas.get('discovered', []))}/{len(NAMED_DUNGEONS)}** named dungeons discovered\n"
                f"🏛️ **{len(atlas.get('completed', []))}/{len(NAMED_DUNGEONS)}** completed • "
                f"📚 **{len(profile.get('season_archive', []))}/12** seasonal chapters archived"
            ),
            inline=False,
        )
        embed.set_footer(text="All navigation is free. Exploration and named-dungeon rooms spend energy only after confirmation.")
        return embed

    @staticmethod
    def _quest_journal_embed(profile: dict[str, Any]) -> discord.Embed:
        state = profile.get("quests_v2", {})
        active_lines = []
        for key, progress in list(state.get("active", {}).items())[:8]:
            definition = QUESTS.get(key, {"name": key, "category": "unknown"})
            marker = "✅" if int(progress["progress"]) >= int(progress["target"]) else "◆"
            active_lines.append(
                f"{marker} **{definition['name']}** · {definition['category'].title()}\n"
                f"`{key}` • {progress['progress']}/{progress['target']}",
            )
        available = [
            quest for quest in available_quests(profile)
            if quest["available"] and not quest["active"] and not quest["completed"]
        ]
        locked = [quest for quest in available_quests(profile) if not quest["available"] and not quest["completed"]]
        available_lines = [
            f"📜 **{quest['name']}** · {quest['category'].title()}\n`{quest['key']}` • {quest['energy']} energy budget"
            for quest in available[:6]
        ]
        locked_lines = [f"🔒 **{quest['name']}** — {quest['reason']}" for quest in locked[:4]]
        embed = discord.Embed(
            title="📜 Persistent Quest Journal",
            description=(
                "Every objective, alternate resolution, and reward claim is saved. "
                "Resolving through different convictions changes future World Echoes."
            ),
            color=0x8E44AD,
        )
        embed.add_field(
            name=f"Active — {len(state.get('active', {}))}",
            value="\n".join(active_lines) or "No active quests.",
            inline=False,
        )
        embed.add_field(
            name=f"Available — {len(available)}",
            value="\n".join(available_lines) or "No quests currently available.",
            inline=False,
        )
        if locked_lines:
            embed.add_field(name="Coming Roads", value="\n".join(locked_lines), inline=False)
        embed.set_footer(
            text="Use the journal selector to accept ready quests or choose their final conviction.",
        )
        return embed

    @staticmethod
    def _living_campaign_embed(profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        view = living_campaign_view(profile)
        if view["complete"]:
            name, text = view["ending"]
            return discord.Embed(
                title=f"📕 The Living Chronicle — {name}",
                description=f"{text}\n\n**18 permanent decisions • {len(view['state']['completed'])}/6 acts complete**",
                color=morality_path(profile)["color"],
            )
        act = view["act"]
        state = view["state"]
        if not view["available"]:
            description = f"🔒 Reach floor **{act['floor']}** to begin.\n\n{act['scenes'][0]}"
        elif view["needs_choice"]:
            decision = act["decisions"][int(state["decision"])]
            description = (
                f"{narrative + chr(10) + chr(10) if narrative else ''}"
                f"**Permanent decision {int(state['decision']) + 1}/3**\n{decision['prompt']}\n\n"
                "Choose `mercy`, `honesty`, `ambition`, or `ruthlessness`."
            )
        else:
            next_scene = int(state["scene"]) + 1
            description = (
                f"{narrative + chr(10) + chr(10) if narrative else ''}"
                f"Scene **{next_scene}/6** is ready. Continuing costs **1 exploration energy**."
            )
        embed = discord.Embed(
            title=f"📖 Act {int(state['act']) + 1}/6 — {act['name']}",
            description=description,
            color=0x6C3483,
        )
        embed.add_field(
            name="Chronicle State",
            value=(
                f"📖 Scene **{state['scene']}/6**\n"
                f"⚖️ Decisions **{state['decision']}/3**\n"
                f"🧭 Energy **{profile['turns']}**"
            ),
        )
        embed.add_field(
            name="Act Reward",
            value=f"{act['reward']['gold']} currency • {act['reward']['xp']} XP • {act['reward']['resolve']} Resolve",
        )
        embed.set_footer(text="Continue the Chronicle from Activities; permanent decisions always ask for confirmation.")
        return embed

    @staticmethod
    def _atlas_embed(profile: dict[str, Any]) -> discord.Embed:
        locations = atlas_locations(profile)
        lines = []
        for location in locations:
            marker = "✅" if location["completed"] else "🗺️" if location["discovered"] else "🔒"
            detail = (
                f"{location['rooms']} rooms • 1 energy/room • {location['mechanic']}"
                if location["discovered"]
                else location["locked_reason"]
            )
            lines.append(f"{marker} **{location['name']}** · floor {location['floor']}\n`{location['key']}` • {detail}")
        run = profile.get("atlas", {}).get("active_dungeon", {})
        run_line = ""
        if run:
            definition = NAMED_DUNGEONS[run["key"]]
            pending = run.get("pending") or {}
            state = (
                f" • choice: {pending.get('name')}"
                if pending
                else " • battle active"
                if run.get("awaiting_combat")
                else ""
            )
            run_line = (
                f"\n\n**Active:** {definition['name']} • room {run['room']}/{definition['rooms']} "
                f"• checkpoint {run['checkpoint']}{state}"
            )
        embed = discord.Embed(
            title="🗺️ The Living Atlas",
            description="\n\n".join(lines) + run_line,
            color=0x2471A3,
        )
        embed.set_footer(
            text="Enter, advance, resolve rooms, and resume battles with the Atlas controls below.",
        )
        return embed

    @staticmethod
    def _mail_embed(profile: dict[str, Any]) -> discord.Embed:
        read = set(profile.get("mail_read", []))
        letters = profile.get("mailbox", [])
        lines = [
            f"{'✉️' if letter['key'] not in read else '📨'} **{letter['subject']}** — {letter['from']}\n{letter['body']}"
            for letter in reversed(letters[-8:])
        ]
        embed = discord.Embed(
            title=f"✉️ Lastlight Post — {sum(letter['key'] not in read for letter in letters)} unread",
            description="\n\n".join(lines) or "No letters have found you yet.",
            color=0xA569BD,
        )
        embed.set_footer(text="Use /deepdelve living mail read. Letters never expire.")
        return embed

    @staticmethod
    def _sanctum_embed(profile: dict[str, Any]) -> discord.Embed:
        state = ensure_sanctum(profile)
        lines = []
        for key, definition in SANCTUM_ROOMS.items():
            level = int(state["rooms"][key])
            cost = sanctum_upgrade_cost(profile, key)
            next_line = "Complete" if cost is None else f"Next: {cost} currency"
            lines.append(f"🏛️ **{definition['name']} {level}/3**\n{definition['benefit']} • `{key}` • {next_line}")
        embed = discord.Embed(
            title="🏛️ Personal Sanctum",
            description="\n\n".join(lines),
            color=0xB7950B,
        )
        embed.set_footer(
            text=(
                f"Lifetime restoration spending: {state['spent']} currency "
                "• Upgrades are capped convenience and cosmetics."
            ),
        )
        return embed

    @staticmethod
    def _collection_codex_embed(profile: dict[str, Any]) -> discord.Embed:
        counts = content_counts()
        nemeses = ensure_nemeses(profile)
        atlas = profile.get("atlas", {})
        embed = discord.Embed(
            title="📚 Collection Codex",
            description="A permanent record of the enemies, treasures, stories, and consequences you have uncovered.",
            color=0x1ABC9C,
        )
        embed.add_field(
            name="Creatures & Rivals",
            value=(
                f"👹 **{len(profile.get('bestiary', {}))}/{counts['enemies']}+** researched entries\n"
                f"👁️ **{len(nemeses['defeated'])}** Nemeses defeated\n"
                f"🏆 **{profile.get('bosses', 0)}** bosses defeated"
            ),
        )
        embed.add_field(
            name="Treasures",
            value=(
                f"🏺 **{len(profile.get('legendary_codex', []))}** legendary discoveries\n"
                f"🧩 **{sum(len(value) for value in profile.get('set_discoveries', {}).values())}** set pieces\n"
                f"📖 **{len(profile.get('recipes', []))}** recipes"
            ),
        )
        embed.add_field(
            name="Chronicle",
            value=(
                f"🗺️ **{len(atlas.get('completed', []))}/{counts['dungeons']}** named dungeons\n"
                f"⚖️ **{len(profile.get('moral_deeds', []))}** remembered deeds\n"
                f"📚 **{len(profile.get('season_archive', []))}/{counts['seasons']}** season chapters"
            ),
            inline=False,
        )
        return embed

    def _adventure_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        if not profile.get("created"):
            return self._not_created_embed()
        stats = self._stats(profile)
        region = region_for_floor(profile["floor"])
        description = narrative or random.choice(region["rooms"])
        embed = discord.Embed(
            title=f"{region['emoji']} {region['name']} — Floor {profile['floor']}",
            description=f"*{region['description']}*\n\n{description}",
            color=region["color"],
        )
        embed.add_field(
            name="Delver",
            value=(
                f"❤️ {profile['hp']}/{stats['max_hp']}  •  🔷 {profile['mana']}/{stats['max_mana']}  •  "
                f"🧪 {profile['potions']}\n"
                f"{morality_path(profile)['emoji']} **{morality_path(profile)['name']}** morality"
            ),
            inline=False,
        )
        embed.add_field(
            name="Expedition",
            value=(
                f"🚪 Room **{profile['rooms_cleared'] + 1}/5**\n"
                f"🧭 **{profile['turns']}** turns remain\n"
                f"🎒 **{len(profile['inventory'])}/25** pack slots"
            ),
        )
        embed.add_field(
            name="Spoils",
            value=(f"🪙 **{self._money(profile, profile['gold'])}**\n✨ **{profile['xp']}/{xp_for_level(profile['level'])}** XP"),
        )
        nodes = profile.get("map_nodes", [])
        unexplored = max(0, 5 - len(nodes))
        embed.add_field(
            name="Dungeon Map",
            value=" — ".join(nodes + ["◈"] + ["·"] * unexplored),
            inline=False,
        )
        mutator = profile.get("floor_mutator") or floor_mutator(profile["floor"])
        embed.add_field(
            name=f"⚠️ Floor Condition — {mutator['name']}",
            value=mutator["description"],
            inline=False,
        )
        embed.set_footer(text="Choose Explore to enter the next room. Daily turns reset at 00:00 UTC.")
        return embed

    def _progression_embed(self, profile: dict[str, Any]) -> discord.Embed:
        details = GAME_CLASSES[profile["class_key"]]
        subclass = subclass_options(profile).get(profile.get("subclass", ""))
        attributes = profile.get("attributes", {})
        embed = discord.Embed(
            title=f"🌟 {profile['character_name']}'s Path",
            description=(
                f"**Base Class:** {details['emoji']} {details['name']}\n**Subclass:** {subclass['emoji']} {subclass['name']}"
                if subclass
                else f"**Base Class:** {details['emoji']} {details['name']}\n**Subclass:** Unlocks at level 10"
            ),
            color=EMBED_COLOR,
        )
        embed.add_field(
            name=f"Attributes • {profile.get('attribute_points', 0)} points",
            value=(
                f"💪 **Might {attributes.get('might', 0)}** — physical power\n"
                f"🦶 **Finesse {attributes.get('finesse', 0)}** — precision and luck\n"
                f"🧠 **Insight {attributes.get('insight', 0)}** — mana reserves\n"
                f"❤️ **Vitality {attributes.get('vitality', 0)}** — health and defense\n"
                f"🎲 **Fortune {attributes.get('fortune', 0)}** — criticals and discoveries"
            ),
            inline=False,
        )
        talent_lines = []
        for talent in TALENT_TREES[profile["class_key"]]:
            rank = profile.get("talents", {}).get(talent["key"], 0)
            talent_lines.append(
                f"◆ **{talent['name']} {rank}/{talent['max']}** — {talent['description']}",
            )
        embed.add_field(
            name=f"Talents • {profile.get('talent_points', 0)} points",
            value="\n".join(talent_lines),
            inline=False,
        )
        ability_lines = [
            f"{ability['emoji']} **{ability['name']}** — {ability['description']}" for ability in available_abilities(profile)
        ]
        embed.add_field(name="Unlocked Abilities", value="\n".join(ability_lines), inline=False)
        background = BACKGROUNDS.get(profile.get("background", ""))
        embed.set_footer(
            text=(
                f"Background: {background['name'] if background else 'Unchosen'} • "
                f"Alignment: {profile.get('alignment', 'Unwritten')}"
            ),
        )
        return embed

    def _choice_embed(self, profile: dict[str, Any]) -> discord.Embed:
        choice = profile["choice"]
        region = region_for_floor(profile["floor"])
        embed = discord.Embed(
            title=f"{choice['emoji']} {choice['title']}",
            description=f"*{region['name']}*\n\n{choice['text']}\n\n**What do you do?**",
            color=region["color"],
        )
        if choice.get("key") == "judgment_mirror":
            score = int(profile.get("morality", 0))
            embed.add_field(
                name=f"⚖️ The Mirror Reads You — {score:+d} Morality",
                value=(
                    "☀️ **Release** requires +30 Radiant\n⚖️ **Negotiate** requires −29 to +29\n🌑 **Devour** requires −30 Umbral"
                ),
                inline=False,
            )
        embed.set_footer(
            text="Your decision is saved. The Deep remembers motive, consequence, and repeated behavior.",
        )
        return embed

    def _puzzle_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        puzzle = profile.get("active_puzzle") or {}
        region = region_for_floor(profile["floor"])
        puzzle_text = puzzle.get("text", "The mechanism waits.")
        lead = narrative or ""
        if lead.strip() == puzzle_text.strip():
            lead = ""
        elif lead.startswith(f"{puzzle_text}\n\n"):
            lead = lead.removeprefix(f"{puzzle_text}\n\n")
        embed = discord.Embed(
            title=f"{puzzle.get('emoji', '🧩')} {puzzle.get('name', 'Dungeon Puzzle')}",
            description=(
                f"*{region['name']}*\n\n{lead + chr(10) + chr(10) if lead else ''}"
                f"{puzzle_text}\n\n"
                "**Choose carefully. A wrong answer has consequences.**"
            ),
            color=0x2980B9,
        )
        embed.add_field(
            name="Insight",
            value=(
                f"🧩 **{len(profile.get('solved_puzzles', []))}** unique puzzles solved\n"
                f"🔥 **{profile.get('puzzle_streak', 0)}** current streak"
            ),
            inline=False,
        )
        embed.set_footer(text="Two failed attempts seal the chamber. Puzzle state is saved.")
        return embed

    def _campaign_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        scene = campaign_scene(profile)
        if scene["complete"]:
            ending = scene["state"].get("ending", "unwritten").title()
            return discord.Embed(
                title="📕 The First Chronicle — Complete",
                description=(
                    f"Your ending: **{ending}**\n\n"
                    "The Deep continues beyond the final page. Your campaign choices remain part of this character forever."
                ),
                color=GOLD_COLOR,
            )
        chapter = scene["chapter"]
        locked = not scene["available"]
        if locked:
            description = f"*{chapter['summary']}*\n\n🔒 Reach floor **{chapter['floor']}** to continue this chapter."
        elif scene["at_choice"]:
            description = (
                f"*{chapter['summary']}*\n\n{narrative + chr(10) + chr(10) if narrative else ''}**{chapter['choice']['prompt']}**"
            )
        else:
            description = f"*{chapter['summary']}*\n\n{narrative or scene['text']}\n\nUse **Continue Story** to advance."
        embed = discord.Embed(
            title=f"{chapter['emoji']} Chapter {chapter['number']} — {chapter['name']}",
            description=description,
            color=0x8E44AD,
        )
        choices = scene["state"].get("choices", {})
        if choices:
            history = []
            for completed in CAMPAIGN_CHAPTERS:
                if completed["key"] in choices:
                    selected = completed["choice"]["options"][choices[completed["key"]]][0]
                    history.append(f"◆ **{completed['name']}:** {selected}")
            embed.add_field(name="Decisions That Endure", value="\n".join(history), inline=False)
        embed.set_footer(
            text=f"{len(scene['state'].get('completed', []))}/{len(CAMPAIGN_CHAPTERS)} chapters complete • "
            f"{profile.get('event_tokens', 0)} Chronicle Tokens",
        )
        return embed

    @staticmethod
    def _tutorial_embed(profile: dict[str, Any]) -> discord.Embed:
        step = int(profile.get("tutorial_step", 0))
        lessons = (
            ("The Chronicle", "Create a delver, then use `/deepdelve adventure` or the Explore button. Every action is saved."),
            (
                "Reading Combat",
                "Enemy intentions reveal the next move. Defend against heavy attacks; exploit guards and recovery turns.",
            ),
            ("Building a Hero", "Spend attributes and talents under `/deepdelve progression`. At level 10, choose a subclass."),
            ("Living Off the Deep", "Equip loot, gather regional materials, choose a profession, and craft at Orra's forge."),
            (
                "A World That Remembers",
                "Campaign choices and major deeds shape Living Morality, NPC reactions, transformations, and Conviction powers.",
            ),
        )
        index = min(step, len(lessons) - 1)
        title, text = lessons[index]
        embed = discord.Embed(
            title=f"🕯️ Delver's Primer {index + 1}/{len(lessons)} — {title}",
            description=text,
            color=EMBED_COLOR,
        )
        embed.add_field(
            name="Next Objective",
            value=(
                "Use `/deepdelve chronicle tutorial` again to read the next lesson."
                if step < len(lessons) - 1
                else "Primer complete. The Deep will teach the rest."
            ),
            inline=False,
        )
        return embed

    def _chronicle_embed(self, profile: dict[str, Any], guild_id: int) -> discord.Embed:
        scene = campaign_scene(profile)
        moral = morality_path(profile)
        chapter_text = "Complete" if scene["complete"] else f"Chapter {scene['chapter']['number']}: {scene['chapter']['name']}"
        active = active_companion(profile)
        companion_text = (
            f"{active[0]['emoji']} {active[0]['name']} • Level {active[1]['level']} • Bond {active[1]['bond']}/100"
            if active
            else "No active companion"
        )
        profession = profile.get("profession", {})
        profession_def = PROFESSIONS.get(profession.get("key", ""))
        profession_text = (
            f"{profession_def['emoji']} {profession_def['name']} • "
            f"Level {profession.get('level', 1)} {profession_rank(int(profession.get('level', 1)))}"
            if profession_def
            else "No profession chosen"
        )
        event = active_world_event(guild_id)
        embed = discord.Embed(
            title="📖 The Living Chronicle",
            description=("Your solo story, discoveries, allies, craft, and the changing state of Lastlight—all in one place."),
            color=0x8E44AD,
        )
        embed.add_field(name="Main Campaign", value=f"📕 {chapter_text}", inline=False)
        embed.add_field(
            name=f"{moral['emoji']} Living Morality",
            value=(
                f"**{moral['name']}** • {int(profile.get('morality', 0)):+d}\n"
                f"**{len(profile.get('moral_deeds', []))}** remembered deeds"
            ),
        )
        embed.add_field(name="Companion", value=companion_text)
        embed.add_field(name="Profession", value=profession_text)
        embed.add_field(
            name=f"{event['emoji']} Today's World Event — {event['name']}",
            value=event["description"],
            inline=False,
        )
        embed.add_field(
            name="Discovery",
            value=(
                f"🧩 **{len(profile.get('solved_puzzles', []))}** puzzles solved\n"
                f"🌍 **{len(profile.get('world_events_seen', []))}** events witnessed\n"
                f"🔸 **{profile.get('event_tokens', 0)}** Chronicle Tokens"
            ),
        )
        embed.add_field(
            name="Commands",
            value=(
                "`campaign` • `morality` • `deeds` • `tutorial` • `puzzle`\n"
                "`companion` • `profession` • `gather` • `world` • `town`"
            ),
        )
        return embed

    @staticmethod
    def _morality_embed(profile: dict[str, Any]) -> discord.Embed:
        moral = morality_path(profile)
        score = int(profile.get("morality", 0))
        convictions = profile.get("convictions", {})
        power = moral_power(profile)
        legacy = ensure_legacy(profile)
        recent = profile.get("moral_deeds", [])[-3:]
        embed = discord.Embed(
            title=f"{moral['emoji']} Living Morality — {moral['name']}",
            description=(
                f"*{moral['appearance']}*\n\n"
                f"🌑 {progress_bar(score + 100, 200, 16)} ☀️\n"
                f"**Morality:** {score:+d}/100\n"
                f"**Origin philosophy:** {profile.get('alignment', 'Unwritten')}"
            ),
            color=moral["color"],
        )
        embed.add_field(
            name="Convictions",
            value=(
                f"🤍 **Mercy {convictions.get('mercy', 0)}** — compassion and sacrifice\n"
                f"👁️ **Honesty {convictions.get('honesty', 0)}** — truth and remembrance\n"
                f"🔥 **Ambition {convictions.get('ambition', 0)}** — power and self-determination\n"
                f"🗡️ **Ruthlessness {convictions.get('ruthlessness', 0)}** — decisive cruelty"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"{power['emoji']} Combat Conviction — {power['name']}",
            value=(
                power["description"]
                if power["available"]
                else (
                    f"Conviction Fatigue: **{power['fatigue']} victories remain**."
                    if power["unlocked"]
                    else "Locked until your actions establish a moral identity."
                )
            ),
            inline=False,
        )
        embed.add_field(
            name=f"Remembered Deeds — {len(profile.get('moral_deeds', []))}",
            value=(
                "\n".join(f"• **{deed['name']}** ({int(deed.get('morality', 0)):+d})" for deed in reversed(recent))
                or "*Your actions have not yet given the Deep an answer.*"
            ),
            inline=False,
        )
        tenet_lines = [
            f"◆ **{TENETS[key]['name']}** — {TENETS[key]['description']}"
            for key in legacy["active_tenets"]
            if key in TENETS
        ]
        embed.add_field(
            name=f"◆ Resolve & Tenets — {legacy['resolve']} Resolve",
            value="\n".join(tenet_lines) or "No Tenets equipped yet.",
            inline=False,
        )
        embed.add_field(
            name="Ideological Factions",
            value="\n".join(
                f"{FACTIONS[key]['emoji']} **{FACTIONS[key]['name']}** — {legacy['faction_reputation'][key]} reputation"
                for key in FACTIONS
            ),
            inline=False,
        )
        journey = legacy.get("redemption") or {}
        if journey:
            embed.add_field(
                name="🛤️ Moral Journey",
                value=(
                    f"Toward **{journey['target'].title()}** • stage {journey['stage']}/3 • "
                    f"{journey['progress']}/{journey['required']} fitting deeds"
                ),
                inline=False,
            )
        embed.set_footer(
            text="Morality changes access and tactics—not total reward value. Easy repeated deeds stop shifting the world.",
        )
        return embed

    @staticmethod
    def _companion_embed(profile: dict[str, Any]) -> discord.Embed:
        active_key = profile.get("active_companion", "")
        owned = profile.get("companions", {})
        lines = []
        for key, definition in COMPANIONS.items():
            progress = owned.get(key)
            bond_line = ""
            if not progress:
                state = f"🔒 Reach floor {definition['unlock_floor']}"
            else:
                marker = " ⭐ ACTIVE" if key == active_key else ""
                needed = 40 + int(progress.get("level", 1)) * 30
                bond = int(progress.get("bond", 0))
                bond_lines = definition.get("bond_lines", ())
                bond_line = bond_lines[min(len(bond_lines) - 1, bond // 35)] if bond_lines else ""
                state = f"Level {progress.get('level', 1)} • XP {progress.get('xp', 0)}/{needed} • Bond {bond}/100{marker}"
            lines.append(
                f"{definition['emoji']} **{definition['name']} — {definition['role']}**\n"
                f"{definition['description']}\n*{definition['passive']}*"
                f"{f'{chr(10)}“{bond_line}”' if progress and bond_line else ''}\n"
                f"`{key}` • {state}",
            )
        embed = discord.Embed(
            title="🐾 Companions of the Deep",
            description="\n\n".join(lines),
            color=0x16A085,
        )
        embed.set_footer(text="Choose a discovered companion from the roster menu below.")
        return embed

    @staticmethod
    def _profession_embed(profile: dict[str, Any]) -> discord.Embed:
        selected = profile.get("profession", {})
        lines = []
        for key, definition in PROFESSIONS.items():
            active = " ⭐ ACTIVE" if selected.get("key") == key else ""
            lines.append(
                f"{definition['emoji']} **{definition['name']}**{active}\n"
                f"{definition['description']}\n*{definition['benefit']}* • `{key}`",
            )
        if selected.get("key"):
            level = int(selected.get("level", 1))
            footer = f"Level {level} {profession_rank(level)} • {selected.get('xp', 0)}/{50 + level * 25} XP"
        else:
            footer = "Your first profession is free. Changing professions costs gold but preserves mastery."
        embed = discord.Embed(
            title="🛠️ Lastlight Professions",
            description="\n\n".join(lines),
            color=0xD68910,
        )
        embed.set_footer(text=footer)
        return embed

    @staticmethod
    def _activities_embed(profile: dict[str, Any]) -> discord.Embed:
        """Summarize menu-accessible long-term activities."""
        profession = profile.get("profession", {})
        profession_def = PROFESSIONS.get(profession.get("key", ""))
        companion = active_companion(profile)
        return discord.Embed(
            title="🎯 Lastlight Activities",
            description=(
                "Choose a system below. Every normal player action is available through menus; "
                "commands are optional shortcuts."
            ),
            color=0x2471A3,
        ).add_field(
            name="Current Calling",
            value=(
                f"{profession_def['emoji']} **{profession_def['name']}**, level {profession.get('level', 1)}"
                if profession_def
                else "🛠️ No profession selected—your first calling is free."
            ),
            inline=False,
        ).add_field(
            name="Expedition Ally",
            value=(
                f"{companion[0]['emoji']} **{companion[0]['name']}**, bond {companion[1]['bond']}/100"
                if companion
                else "🐾 No active companion."
            ),
            inline=False,
        ).add_field(
            name="Living World",
            value=(
                f"📖 Saga acts completed: **{len(profile.get('living_campaign', {}).get('completed', []))}/6**\n"
                f"🗄️ Seasonal chapters archived: **{len(profile.get('season_archive', []))}/12**\n"
                f"⚒️ Weekly commissions completed: **{profile.get('commissions', {}).get('completed', 0)}**"
            ),
            inline=False,
        )

    @staticmethod
    def _commissions_embed(profile: dict[str, Any]) -> discord.Embed:
        offers = commission_board(profile)
        active = profile.get("commissions", {}).get("active") or {}
        lines = [
            (
                f"**{index}. {offer['name']}**\n"
                f"{offer['objective'].title()} {offer['target']} • "
                f"{offer['reward']['gold']} currency • {offer['reward']['xp']} XP"
            )
            for index, offer in enumerate(offers, start=1)
        ]
        if active:
            lines.insert(
                0,
                f"⭐ **Active: {active['name']}** — {active['progress']}/{active['target']}\n",
            )
        embed = discord.Embed(
            title="⚒️ Weekly Profession Commissions",
            description="\n\n".join(lines),
            color=0xB9770E,
        )
        embed.set_footer(
            text="Choose an offer from the menu. Only one weekly commission may be active at a time.",
        )
        return embed

    @staticmethod
    def _season_archive_embed(profile: dict[str, Any]) -> discord.Embed:
        statuses = season_chapter_status(profile)
        lines = []
        for status in statuses:
            marker = "✅" if status["completed"] else "📖" if status["active"] else "📚" if status["available"] else "🔒"
            reason = (
                "Archived permanently"
                if status["completed"]
                else "Active"
                if status["active"]
                else "Available now"
                if status["available"]
                else status["locked_reason"]
            )
            lines.append(f"{marker} **{status['index']}. {status['name']}** — {reason}")
        active = profile.get("season_story", {})
        active_line = (
            f"\n\n**Active chapter:** `{active.get('active')}` • scene {active.get('scene', 0)}/3"
            if active.get("active")
            else ""
        )
        return discord.Embed(
            title="🗄️ Permanent Season Archive",
            description="\n".join(lines) + active_line,
            color=0x5B2C6F,
        )

    @staticmethod
    def _world_event_embed(guild_id: int) -> discord.Embed:
        event = active_world_event(guild_id)
        special = {
            "lantern_festival": "\n🏘️ Lastlight services: **15% cheaper**",
            "hollow_march": "\n👑 Elite encounter chance: **greatly increased**",
            "shifting_stairs": "\n🧩 Puzzle chambers: **greatly increased**",
        }.get(event["key"], "")
        embed = discord.Embed(
            title=f"{event['emoji']} World Event — {event['name']}",
            description=event["description"],
            color=0x5B2C6F,
        )
        embed.add_field(
            name="Today's Effects",
            value=(
                f"⚔️ Enemy power: **{round(event['combat'] * 100)}%**\n"
                f"🎁 Combat rewards: **{round(event['reward'] * 100)}%**\n"
                f"🧩 Puzzle frequency/rewards: **{round(event['puzzle'] * 100)}%**"
                f"{special}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Server-specific event • {event['date']} UTC • Changes daily")
        return embed

    def _town_development_embed(self, profile: dict[str, Any], town: dict[str, Any]) -> discord.Embed:
        lines = []
        for key, definition in TOWN_BUILDINGS.items():
            level = int(town.get("buildings", {}).get(key, 0))
            if level >= 4:
                progress = "MAXIMUM"
            else:
                cost = definition["costs"][level]
                progress = f"Next: {self._money(profile, cost)}"
            lines.append(
                f"{definition['emoji']} **{definition['name']} — {level}/4**\n{definition['description']} • {progress}",
            )
        embed = discord.Embed(
            title=f"🏘️ Lastlight Reborn — Town Level {town.get('level', 1)}",
            description=(
                "Every delver can fund Lastlight. Server administrators choose which building the shared treasury upgrades."
            ),
            color=SUCCESS_COLOR,
        )
        embed.add_field(name="Town Works", value="\n\n".join(lines), inline=False)
        embed.add_field(
            name="Shared Treasury",
            value=f"🪙 **{self._money(profile, int(town.get('treasury', 0)))}**",
        )
        embed.add_field(
            name="Your Legacy",
            value=f"🏗️ **{self._money(profile, int(profile.get('town_contribution', 0)))} contributed**",
        )
        embed.set_footer(text="Contribute with /deepdelve chronicle contribute amount:<gold>.")
        return embed

    @staticmethod
    def _not_created_embed() -> discord.Embed:
        return discord.Embed(
            title="🕯️ No chronicle found",
            description="Create a character with `/deepdelve create` to enter the dungeon.",
            color=DANGER_COLOR,
        )

    @staticmethod
    def _hardcore_death_embed(profile: dict[str, Any]) -> discord.Embed:
        return discord.Embed(
            title=f"🪦 The Chronicle of {profile['character_name']} Has Ended",
            description=(
                f"This Hardcore delver reached floor **{profile['deepest_floor']}**, "
                f"defeated **{profile['kills']} enemies** and **{profile['bosses']} bosses**, "
                "then died permanently.\n\nUse `/deepdelve retire` to archive this character "
                "and begin another legend."
            ),
            color=0x1B1B1B,
        )

    def _combat_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        enemy = profile["encounter"]
        stats = self._stats(profile)
        title_prefix = "👑 BOSS — " if enemy.get("boss") else ""
        embed = discord.Embed(
            title=f"{enemy['emoji']} {title_prefix}{enemy['name']}",
            description=narrative or enemy.get("description", "Steel yourself—the creature advances!"),
            color=DANGER_COLOR if enemy.get("boss") else 0xD35400,
        )
        embed.add_field(
            name="Enemy",
            value=(
                f"❤️ `{enemy['hp']}/{enemy['max_hp']}` {progress_bar(enemy['hp'], enemy['max_hp'])}\n"
                f"⚔️ {enemy['attack']} ATK  •  🛡️ {enemy['defense']} DEF"
            ),
            inline=False,
        )
        embed.add_field(
            name=profile["character_name"],
            value=(
                f"❤️ `{profile['hp']}/{stats['max_hp']}` {progress_bar(profile['hp'], stats['max_hp'])}\n"
                f"🔷 `{profile['mana']}/{stats['max_mana']}`  •  🧪 `{profile['potions']}`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎯 Enemy Intention",
            value=intent_description(enemy),
            inline=False,
        )
        ability_lines = []
        cooldowns = profile.get("skill_cooldowns", {})
        for ability in available_abilities(profile):
            cooldown = int(cooldowns.get(ability["key"], 0))
            state = f"CD {cooldown}" if cooldown else f"{ability['mana']} mana"
            ability_lines.append(f"{ability['emoji']} **{ability['name']}** — {state}")
        embed.add_field(name="Abilities", value="\n".join(ability_lines), inline=False)
        affix = enemy.get("affix") or {}
        if affix:
            effect = affix.get("effect") or "enhanced combat attributes"
            embed.add_field(
                name=f"{affix['emoji']} Elite Affix: {affix['name']}",
                value=f"This creature possesses {effect}. Rewards are substantially increased.",
                inline=False,
            )
        if profile.get("status"):
            status_lines = [
                f"☠️ **{name.title()}** — {turns} turn{'s' if turns != 1 else ''}"
                for name, turns in profile["status"].items()
                if turns > 0
            ]
            if status_lines:
                embed.add_field(name="Conditions", value="\n".join(status_lines), inline=False)
        embed.set_footer(text="Combat progress is saved. You can resume it with /deepdelve adventure.")
        return embed

    def _inventory_embed(
        self,
        profile: dict[str, Any],
        selected_id: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎒 {profile['character_name']}'s Pack",
            description="Select an item, then use the buttons below. Unidentified relics can be revealed here.",
            color=EMBED_COLOR,
        )
        inventory = profile.get("inventory", [])
        if not inventory:
            embed.description = "Your pack is empty. The dungeon is full of equipment waiting to be found."
        else:
            lines = []
            for index, item in enumerate(inventory, start=1):
                rarity = RARITIES[int(item.get("rarity_index", 0))]
                selected = " ◀" if str(item["id"]) == selected_id else ""
                lines.append(
                    f"{rarity['emoji']} **{index}. {item['name']}** `{item['id']}`{selected}\n"
                    f"└ {item_stat_line(item)} • 🪙 {item['value']}",
                )
            embed.description = "\n".join(lines)
        equip_lines = []
        for slot in ("weapon", "armor", "charm"):
            item = profile["equipment"].get(slot)
            equip_lines.append(f"**{slot.title()}:** {item['name'] if item else 'Empty'}")
        embed.add_field(name="Currently Equipped", value="\n".join(equip_lines), inline=False)
        selected = next(
            (item for item in inventory if str(item["id"]) == selected_id),
            None,
        )
        if selected:
            if not selected.get("identified", True):
                inspection = (
                    f"{item_detail(selected)}\n"
                    f"🔮 Identification cost: **{3 + int(selected.get('rarity_index', 0))} arcane shards**\n"
                    "Use the **Identify** button to reveal its identity and powers."
                )
            else:
                currency_cost, shard_cost = upgrade_cost(selected)
                equipped = profile["equipment"].get(selected["slot"])
                comparison = ""
                if equipped:
                    deltas = []
                    for stat, label in (
                        ("attack", "ATK"),
                        ("defense", "DEF"),
                        ("hp", "HP"),
                        ("luck", "LUCK"),
                    ):
                        delta = int(selected.get(stat, 0)) - int(equipped.get(stat, 0))
                        if delta:
                            deltas.append(f"{delta:+} {label}")
                    comparison = f"\n↔️ vs. **{equipped['name']}**: " + (
                        " • ".join(deltas) if deltas else "equal base attributes"
                    )
                inspection = (
                    f"{item_detail(selected)}\n"
                    f"⬆️ Next upgrade: {self._money(profile, currency_cost)} + "
                    f"{shard_cost} shards{comparison}"
                )
            embed.add_field(
                name="Item Inspection",
                value=inspection,
                inline=False,
            )
        _set_stats, set_effects = equipment_set_bonuses(profile.get("equipment", {}))
        if set_effects:
            embed.add_field(name="Active Set Bonuses", value="\n".join(set_effects), inline=False)
        embed.set_footer(
            text=(
                f"{len(inventory)}/25 pack slots • {self._money(profile, profile['gold'])} • "
                f"{profile.get('arcane_shards', 0)} arcane shards"
            ),
        )
        return embed

    def _town_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        stats = self._stats(profile)
        embed = discord.Embed(
            title="🏘️ Lastlight Outpost",
            description=narrative or "Lanterns glow behind sturdy walls. For a moment, the Deep feels far away.",
            color=SUCCESS_COLOR,
        )
        embed.add_field(
            name="The Gilded Cot",
            value=(
                f"Restore all health for **{self._money(profile, self._rest_price(profile))}**.\n"
                f"❤️ {profile['hp']}/{stats['max_hp']}"
            ),
        )
        embed.add_field(
            name="Apothecary",
            value=(
                f"Buy one healing potion for **{self._money(profile, self._potion_price(profile))}**.\n"
                f"🧪 {profile['potions']} owned"
            ),
        )
        embed.add_field(
            name="Silent Chapel",
            value=(
                f"Restore all mana for **{self._money(profile, max(5, profile['level'] * 3))}**.\n"
                f"🔷 {profile['mana']}/{stats['max_mana']}"
            ),
            inline=False,
        )
        contract = profile.get("active_contract") or {}
        if contract:
            contract_text = (
                f"**{contract['title']}**\n"
                f"{contract['progress']}/{contract['target']} enemies • "
                f"{self._money(profile, contract['gold'])} + {contract['xp']} XP"
            )
        else:
            contract_text = "No active contract. Take one from the notice board."
        embed.add_field(name="Contract Board", value=contract_text, inline=False)
        legacy = ensure_legacy(profile)
        contacts = [
            f"{FACTIONS[key]['emoji']} **{FACTIONS[key]['name']}** — "
            + (
                f"contact unlocked (`/deepdelve living service {key}`)"
                if int(legacy["faction_reputation"][key]) >= 10
                else f"{legacy['faction_reputation'][key]}/10 reputation"
            )
            for key in FACTIONS
        ]
        embed.add_field(name="Faction Contacts", value="\n".join(contacts), inline=False)
        embed.set_footer(text=f"You carry {self._money(profile, profile['gold'])}.")
        return embed

    def _craft_embed(self, profile: dict[str, Any], narrative: str | None = None) -> discord.Embed:
        region = region_for_floor(profile["floor"])
        material_key = region["material"]
        material = MATERIALS[material_key]
        cost = self._craft_cost(profile)
        embed = discord.Embed(
            title="⚒️ Orra's Deepforge",
            description=(
                narrative
                or "The smith studies every scar on your equipment before speaking. "
                "“The Deep remembers what it makes. Let us give it something worth remembering.”"
            ),
            color=0xA04000,
        )
        lines = []
        for key, details in MATERIALS.items():
            lines.append(f"{details['emoji']} **{details['name']}:** {profile['materials'].get(key, 0)}")
        embed.add_field(name="Materials", value="\n".join(lines), inline=False)
        embed.add_field(
            name="Current Recipe",
            value=(
                f"Each item costs **3 {material['name']}** and "
                f"**{self._money(profile, cost)}**.\n"
                f"Your current depth produces floor **{profile['floor'] + 2}** quality equipment."
            ),
            inline=False,
        )
        embed.set_footer(text="Crafted gear is placed in your pack. Three open slots are recommended.")
        return embed

    @staticmethod
    def _world_boss_embed(record: dict[str, Any]) -> discord.Embed:
        if not record:
            return discord.Embed(
                title="🌌 The World Is Quiet",
                description="No world boss currently threatens Lastlight.",
                color=SUCCESS_COLOR,
            )
        hp = int(record["hp"])
        maximum = int(record["max_hp"])
        contributions = sorted(
            record.get("contributions", {}).items(),
            key=lambda entry: entry[1],
            reverse=True,
        )
        leaders = (
            "\n".join(f"<@{user_id}> — **{damage} damage**" for user_id, damage in contributions[:5])
            or "No delver has struck yet."
        )
        embed = discord.Embed(
            title=f"{record['emoji']} WORLD BOSS — {record['name']}",
            description=(
                f"*{record['description']}*\n\n"
                f"❤️ `{hp}/{maximum}` {progress_bar(hp, maximum, 16)}\n"
                "Every delver may strike once every 30 seconds."
            ),
            color=DANGER_COLOR,
        )
        embed.add_field(name="Raid Leaders", value=leaders, inline=False)
        embed.set_footer(text="World-boss victories award currency, XP, season points, and guild renown.")
        return embed

    @staticmethod
    def _rest_price(profile: dict[str, Any]) -> int:
        base = 18 + int(profile["level"]) * 4 + int(profile.get("floor", 1))
        discount = min(0.15, int(profile.get("reputation", 0)) * 0.002)
        discount += float(profile.get("town_bonus", {}).get("service_discount", 0))
        if "clean_hands" in profile.get("legacy", {}).get("active_tenets", []):
            discount += 0.1
        if profile.get("world_event", {}).get("key") == "lantern_festival":
            discount += 0.15
        return max(1, round(base * (1 - discount)))

    @staticmethod
    def _potion_price(profile: dict[str, Any]) -> int:
        base = 35 + int(profile["level"]) * 4 + int(profile.get("floor", 1))
        discount = min(0.15, int(profile.get("reputation", 0)) * 0.002)
        discount += float(profile.get("town_bonus", {}).get("service_discount", 0))
        if profile.get("world_event", {}).get("key") == "lantern_festival":
            discount += 0.15
        if profile.get("profession", {}).get("key") == "alchemist":
            discount += min(0.2, int(profile["profession"].get("level", 1)) * 0.01)
        return max(1, round(base * (1 - discount)))

    @staticmethod
    def _craft_cost(profile: dict[str, Any]) -> int:
        base = 80 + int(profile["level"]) * 12 + int(profile.get("floor", 1)) * 4
        orra_reputation = int(profile.get("npc_reputation", {}).get("orra", 0))
        discount = min(0.25, orra_reputation * 0.01)
        discount += float(profile.get("town_bonus", {}).get("craft_discount", 0))
        if profile.get("profession", {}).get("key") == "blacksmith":
            discount += min(0.2, int(profile["profession"].get("level", 1)) * 0.01)
        return max(1, round(base * (1 - min(0.65, discount))))

    async def _channel_allowed(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            await ctx.send("DeepDelve can only be played inside a server.")
            return False
        guild_data = await self.config.guild(ctx.guild).all()
        if not guild_data["enabled"]:
            await ctx.send("DeepDelve is currently disabled in this server.")
            return False
        channel_id = int(guild_data["adventure_channel"])
        if channel_id and ctx.channel.id != channel_id:
            channel = ctx.guild.get_channel(channel_id)
            destination = channel.mention if channel else f"<#{channel_id}>"
            await ctx.send(f"Adventures are restricted to {destination}.")
            return False
        return True

    async def _require_character(self, ctx: commands.Context) -> dict[str, Any] | None:
        if not await self._channel_allowed(ctx):
            return None
        profile = await self._get_profile(ctx.guild.id, ctx.author.id)
        if not profile["created"]:
            await ctx.send(embed=self._not_created_embed())
            return None
        if not profile.get("origin_complete", True):
            await ctx.send(
                embed=self._origin_embed(profile),
                view=OriginView(self, ctx.author.id, profile),
            )
            return None
        if profile.get("hardcore_dead"):
            await ctx.send(
                "🪦 This Hardcore chronicle has ended permanently. Use `/deepdelve retire` to begin a new character.",
            )
            return None
        return profile

    async def _handle_explore_interaction(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_data = await self.config.guild(interaction.guild).all()
        if not guild_data["enabled"]:
            await interaction.followup.send("DeepDelve is currently disabled here.", ephemeral=True)
            return
        channel_id = int(guild_data["adventure_channel"])
        if channel_id and interaction.channel_id != channel_id:
            await interaction.followup.send(
                f"Adventures are restricted to <#{channel_id}>.",
                ephemeral=True,
            )
            return
        profile, narrative = await self._explore(interaction.guild.id, interaction.user.id)
        if not profile["created"]:
            await interaction.edit_original_response(embed=self._not_created_embed(), view=None)
        elif not profile.get("origin_complete", True):
            await interaction.edit_original_response(
                embed=self._origin_embed(profile),
                view=OriginView(self, interaction.user.id, profile),
            )
        elif profile.get("hardcore_dead"):
            await interaction.edit_original_response(
                embed=self._hardcore_death_embed(profile),
                view=None,
            )
        elif profile["encounter"]:
            await interaction.edit_original_response(
                embed=self._combat_embed(profile, narrative),
                view=CombatView(self, interaction.user.id, profile),
            )
        elif profile["choice"]:
            await interaction.edit_original_response(
                embed=self._choice_embed(profile),
                view=ChoiceView(self, interaction.user.id, profile["choice"]),
            )
        elif profile.get("active_puzzle"):
            await interaction.edit_original_response(
                embed=self._puzzle_embed(profile, narrative),
                view=PuzzleView(self, interaction.user.id, profile["active_puzzle"]),
            )
        else:
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile, narrative),
                view=AdventureView(self, interaction.user.id),
            )

    async def _explore(self, guild_id: int, user_id: int) -> tuple[dict[str, Any], str]:
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            if not profile["created"]:
                return profile, ""
            if not profile.get("origin_complete", True):
                return profile, "Finish writing your origin before entering the Deep."
            if profile.get("hardcore_dead"):
                return profile, "This Hardcore chronicle has ended."
            if profile["encounter"]:
                return profile, "The battle is still waiting for you."
            if profile["choice"]:
                return profile, "The dungeon is waiting for your decision."
            if profile.get("active_puzzle"):
                return profile, "The puzzle chamber is waiting for your answer."
            if profile["turns"] <= 0:
                return profile, "You are too exhausted to continue. Your turns reset at **00:00 UTC**."

            descent = ""
            if profile["rooms_cleared"] >= 5:
                profile["floor"] += 1
                profile["rooms_cleared"] = 0
                profile["map_nodes"] = []
                profile["free_revive"] = True
                profile["combat_flags"].pop("legendary_rebirth", None)
                profile["deepest_floor"] = max(profile["deepest_floor"], profile["floor"])
                profile["floor_mutator"] = floor_mutator(
                    profile["floor"],
                    profile.get("ascensions", 0),
                )
                descent = f"You descend to **floor {profile['floor']}**. "

            profile["turns"] -= 1
            progress_lines = [
                *progress_quests(profile, "explore"),
                *progress_oath(profile, "explore"),
            ]
            progress_text = f"\n\n{chr(10).join(progress_lines)}" if progress_lines else ""
            floor = int(profile["floor"])
            if not profile.get("floor_mutator"):
                profile["floor_mutator"] = floor_mutator(
                    floor,
                    profile.get("ascensions", 0),
                )
            mutator = profile["floor_mutator"]
            world_event = active_world_event(guild_id)
            difficulty = float(await self.config.guild_from_id(guild_id).content_multiplier())
            event_combat = float(world_event["combat"])
            if event_combat > 1:
                safety = float(profile.get("town_bonus", {}).get("event_safety", 0))
                event_combat = 1 + (event_combat - 1) * (1 - safety)
            if world_event["key"] not in profile.get("world_events_seen", []):
                profile["world_events_seen"].append(world_event["key"])
                self._journal(profile, f"World event witnessed: {world_event['name']}.")

            if profile["rooms_cleared"] == 4 and floor % 5 == 0:
                self._map_node(profile, "👑")
                profile["combat_flags"] = {}
                boss = boss_for_floor(floor)
                for stat in ("hp", "attack", "defense"):
                    boss[stat] = max(1, round(boss[stat] * difficulty))
                boss["max_hp"] = boss["hp"]
                boss["attack"] = max(1, round(boss["attack"] * event_combat))
                boss["gold"] = max(1, round(boss["gold"] * max(0.8, difficulty**0.5)))
                boss["xp"] = max(1, round(boss["xp"] * max(0.8, difficulty**0.5)))
                boss["event_reward"] = float(world_event["reward"])
                if mutator["key"] == "flooded":
                    boss["attack"] = max(1, round(boss["attack"] * 0.92))
                elif mutator["key"] in {"unstable", "hunted"}:
                    boss["attack"] = max(1, round(boss["attack"] * 1.06))
                    boss["gold"] = round(boss["gold"] * 1.12)
                    boss["xp"] = round(boss["xp"] * 1.08)
                boss["mutator"] = mutator["key"]
                profile["encounter"] = ensure_enemy_intent(boss)
                profile["discovered"] = self._append_unique(
                    profile["discovered"],
                    profile["encounter"]["name"],
                )
                await self._save_profile(guild_id, user_id, profile, starting_gold)
                return profile, descent + profile["encounter"]["description"] + progress_text

            secret_chance = 0.035
            if mutator["key"] == "darkness":
                secret_chance += 0.025
            if "secrets" in equipment_effects(profile.get("equipment", {})):
                secret_chance += 0.03
            if random.random() < secret_chance:
                profile["rooms_cleared"] += 1
                profile["secret_rooms"] = int(profile.get("secret_rooms", 0)) + 1
                self._map_node(profile, "🚪")
                narrative = (
                    "A false wall exhales cold air. Beyond it waits a chamber erased from every map.\n"
                    + self._treasure_event(profile)
                )
                await self._save_profile(guild_id, user_id, profile, starting_gold)
                return profile, descent + narrative + progress_text

            roll = random.random()
            if roll < 0.52:
                self._map_node(profile, "⚔️")
                profile["combat_flags"] = {}
                enemy = apply_affix(enemy_for_floor(floor), floor)
                miniboss_chance = 0.18 if mutator["key"] == "hunted" else 0.08
                if random.random() < miniboss_chance:
                    enemy = apply_miniboss(enemy, floor)
                if world_event["key"] == "hollow_march" and random.random() < 0.5:
                    enemy = self._force_affix(enemy)
                for stat in ("hp", "attack", "defense"):
                    enemy[stat] = max(1, round(enemy[stat] * difficulty))
                enemy["max_hp"] = enemy["hp"]
                enemy["gold"] = max(1, round(enemy["gold"] * max(0.8, difficulty**0.5)))
                enemy["xp"] = max(1, round(enemy["xp"] * max(0.8, difficulty**0.5)))
                enemy["attack"] = max(1, round(enemy["attack"] * event_combat))
                enemy["event_reward"] = float(world_event["reward"])
                if mutator["key"] == "flooded":
                    enemy["attack"] = max(1, round(enemy["attack"] * 0.9))
                elif mutator["key"] == "unstable":
                    enemy["attack"] = max(1, round(enemy["attack"] * 1.08))
                    enemy["gold"] = round(enemy["gold"] * 1.08)
                elif mutator["key"] == "hunted":
                    enemy["gold"] = round(enemy["gold"] * 1.12)
                    enemy["xp"] = round(enemy["xp"] * 1.08)
                enemy["mutator"] = mutator["key"]
                if profile.get("active_companion") == "nocturne" and enemy.get("affix"):
                    enemy["attack"] = max(1, round(enemy["attack"] * 0.9))
                    enemy["defense"] = max(0, round(enemy["defense"] * 0.9))
                nemeses = ensure_nemeses(profile)["active"]
                if nemeses and random.random() < 0.08:
                    nemesis = random.choice(nemeses)
                    enemy["name"] = nemesis["name"]
                    enemy["nemesis_id"] = nemesis["id"]
                    scale = 1 + int(nemesis["level"]) * 0.08
                    enemy["hp"] = max(1, round(enemy["hp"] * scale))
                    enemy["max_hp"] = enemy["hp"]
                    enemy["attack"] = max(1, round(enemy["attack"] * (1 + int(nemesis["level"]) * 0.04)))
                    enemy["gold"] = max(1, round(enemy["gold"] * float(nemesis["reward_multiplier"])))
                    enemy["xp"] = max(1, round(enemy["xp"] * float(nemesis["reward_multiplier"])))
                    enemy["description"] = f"Your Nemesis has found you again. {nemesis['trait_text']}"
                profile["encounter"] = ensure_enemy_intent(enemy)
                profile["discovered"] = self._append_unique(
                    profile["discovered"],
                    profile["encounter"]["name"],
                )
                await self._save_profile(guild_id, user_id, profile, starting_gold)
                region = region_for_floor(floor)
                return profile, descent + random.choice(region["rooms"]) + progress_text

            if roll < 0.64:
                profile["rooms_cleared"] += 1
                self._map_node(profile, "🎁")
                narrative = self._treasure_event(profile)
            elif roll < 0.73:
                profile["rooms_cleared"] += 1
                self._map_node(profile, "✨")
                narrative = self._shrine_event(profile)
            elif roll < 0.73 + 0.09 * float(world_event["puzzle"]):
                self._map_node(profile, "🧩")
                profile["active_puzzle"] = puzzle_for_floor(
                    floor,
                    profile.get("solved_puzzles", []),
                )
                narrative = "A puzzle chamber seals behind you. Its mechanism waits for an answer."
            elif roll < 0.91:
                self._map_node(profile, "❔")
                choice = dict(random.choice(CHOICES))
                choice["options"] = [list(option) for option in choice["options"]]
                profile["choice"] = choice
                narrative = choice["text"]
            elif roll < 0.965:
                profile["rooms_cleared"] += 1
                self._map_node(profile, "⚠️")
                narrative = self._trap_event(profile)
                if profile["hp"] <= 0:
                    narrative += "\n\n" + self._apply_death(profile, "the dungeon's traps")
            else:
                profile["rooms_cleared"] += 1
                self._map_node(profile, "🧙")
                if random.random() < 0.45:
                    gathered = gather(profile)
                    narrative = (
                        f"You discover a rare gathering site and recover "
                        f"{gathered['emoji']} **{gathered['amount']} {gathered['name']}**."
                    )
                    if gathered["potion"]:
                        narrative += "\n⚗️ Your alchemical instincts produce **one bonus potion**."
                    if gathered["messages"]:
                        narrative += "\n" + "\n".join(gathered["messages"])
                else:
                    narrative = self._wanderer_event(profile)

            achievement_text = self._award_achievements(profile)
            if achievement_text:
                narrative += f"\n\n{achievement_text}"
            await self._save_profile(guild_id, user_id, profile, starting_gold)
            return profile, descent + narrative + progress_text

    def _treasure_event(self, profile: dict[str, Any]) -> str:
        stats = self._stats(profile)
        hollow = profile.get("floor_mutator", {}).get("key") == "hollow"
        if random.random() < (0.78 if hollow else 0.68):
            item = self._generate_item(profile, profile["floor"], stats["luck"])
            return "A half-buried chest clicks open beneath your hand.\n" + self._store_loot(profile, item)
        if random.random() < 0.35:
            key, consumable = roll_consumable(profile["floor"])
            profile["consumables"][key] = int(profile["consumables"].get(key, 0)) + 1
            return (
                "A narrow compartment opens beneath the coffer.\n"
                f"{consumable['emoji']} **{consumable['name']}** — {consumable['description']}"
            )
        gold = random.randint(12, 25) + profile["floor"] * random.randint(3, 6)
        if hollow:
            gold = round(gold * 1.15)
        profile["gold"] += gold
        return f"A stone coffer contains **{self._money(profile, gold)}**. Not every treasure needs a curse."

    def _shrine_event(self, profile: dict[str, Any]) -> str:
        stats = self._stats(profile)
        healing_scale = 0.65 if profile.get("floor_mutator", {}).get("key") == "flooded" else 1.0
        moral_key = morality_path(profile)["key"]
        if random.random() < 0.5:
            if moral_key in {"radiant", "beacon"}:
                healing_scale *= 1.15
            healed = min(
                stats["max_hp"] - profile["hp"],
                max(8, round(stats["max_hp"] * 0.35 * healing_scale)),
            )
            profile["hp"] += healed
            return f"A forgotten shrine answers your touch. Warm light restores **{healed} health**."
        if moral_key in {"umbral", "dreadbound"}:
            healing_scale *= 1.15
        restored = min(
            stats["max_mana"] - profile["mana"],
            max(5, round(stats["max_mana"] * 0.45 * healing_scale)),
        )
        profile["mana"] += restored
        return f"Silver fire rises from an ancient brazier, restoring **{restored} mana**."

    def _trap_event(self, profile: dict[str, Any]) -> str:
        stats = self._stats(profile)
        companion_bonus = 10 if profile.get("active_companion") == "brindle" else 0
        dodge_chance = min(65, 12 + stats["luck"] * 2 + companion_bonus)
        if random.randint(1, 100) <= dodge_chance:
            return "A pressure plate sinks beneath your boot—but you spring clear before the blades fall."
        damage = max(3, random.randint(7, 14) + profile["floor"] * 2 - stats["defense"] // 3)
        profile["hp"] -= damage
        return f"Hidden darts tear from the walls. You suffer **{damage} damage**."

    def _wanderer_event(self, profile: dict[str, Any]) -> str:
        if random.random() < 0.16:
            path = morality_path(profile)
            if path["key"] in {"radiant", "beacon"}:
                profile["reputation"] += 1
                return (
                    "A frightened expedition recognizes the warmth surrounding you. "
                    "They refuse payment for their map. **+1 Lastlight reputation.**"
                )
            if path["key"] in {"umbral", "dreadbound"}:
                tribute = 12 + profile["floor"] * 3
                profile["gold"] += tribute
                profile["reputation"] = max(0, profile["reputation"] - 1)
                return (
                    "A scavenger sees the second shadow at your feet and abandons their purse. "
                    f"You take **{self._money(profile, tribute)}**, but Lastlight hears why."
                )
            insight = 10 + profile["floor"] * 2
            profile["xp"] += insight
            return (
                "A cartographer tests three versions of the same route against your patient questions. "
                f"The exchange grants **{insight} XP**."
            )
        if not profile.get("active_rumor") and random.random() < 0.3:
            rumor = create_rumor(profile)
            return (
                "A hooded cartographer refuses coin. Instead, they press a marked route into your hand.\n"
                f"📜 **Rumor: {rumor['name']}** — {rumor['description']}"
            )
        if random.random() < 0.55:
            profile["potions"] += 1
            return (
                "A masked wanderer shares a fire with you, then vanishes without a word.\n"
                "Beside the ashes rests **one healing potion**."
            )
        gold = 20 + profile["floor"] * 5
        if profile["gold"] >= gold:
            profile["gold"] -= gold
            profile["turns"] += 2
            return (
                f"A cartographer sells you a shortcut for **{self._money(profile, gold)}**. "
                "The map grants **two additional turns**."
            )
        return "A cartographer offers a valuable map, but its price is beyond your purse."

    @staticmethod
    def _append_unique(values: list[str], value: str) -> list[str]:
        if value not in values:
            values.append(value)
        return values

    @staticmethod
    def _map_node(profile: dict[str, Any], symbol: str) -> None:
        profile["map_nodes"] = (profile.get("map_nodes", []) + [symbol])[-5:]

    @staticmethod
    def _passes_test(profile: dict[str, Any], chance: int) -> bool:
        rolls = 2 if "key" in equipment_effects(profile.get("equipment", {})) else 1
        return any(random.randint(1, 100) <= chance for _ in range(rolls))

    @staticmethod
    def _journal(profile: dict[str, Any], text: str) -> None:
        entry = f"Floor {profile['floor']} — {text}"
        profile["journal"] = (profile.get("journal", []) + [entry])[-30:]

    def _discover_lore(self, profile: dict[str, Any]) -> str:
        undiscovered = [fragment for fragment in LORE_FRAGMENTS if fragment["title"] not in profile["lore"]]
        if not undiscovered:
            gold = 35 + profile["floor"] * 3
            profile["gold"] += gold
            return f"The inscription repeats a known secret. You recover **{self._money(profile, gold)}** nearby."
        fragment = random.choice(undiscovered)
        profile["lore"].append(fragment["title"])
        self._journal(profile, f"Recovered the lore fragment “{fragment['title']}.”")
        return f"📜 **Lore Recovered: {fragment['title']}**\n*{fragment['text']}*"

    async def _choice_interaction(self, interaction: discord.Interaction, action: str) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            choice = profile.get("choice") or {}
            if not choice:
                await interaction.followup.send("That decision has already been resolved.", ephemeral=True)
                return
            valid_actions = {option[0] for option in choice.get("options", [])}
            if action not in valid_actions:
                await interaction.followup.send("That path is no longer available.", ephemeral=True)
                return
            deaths_before = profile["deaths"]
            potions_before = profile["potions"]
            gold_before = profile["gold"]
            morality_before = int(profile.get("morality", 0))
            narrative = self._resolve_choice(profile, choice["key"], action)
            performed = True
            if choice["key"] == "lost_delver" and action == "aid":
                performed = profile["potions"] < potions_before
            elif choice["key"] == "dark_altar" and action == "offer":
                performed = profile["gold"] < gold_before
            elif choice["key"] == "judgment_mirror":
                performed = (
                    (action == "absolve" and morality_before >= 30)
                    or (action == "consume" and morality_before <= -30)
                    or (action == "bargain" and -29 <= morality_before <= 29)
                )
            deed_lines = record_choice_deed(
                profile,
                choice["key"],
                action,
                performed=performed,
            )
            if deed_lines:
                narrative += "\n\n" + "\n".join(deed_lines)
                deed = profile.get("moral_deeds", [])[-1]
                applied = deed.get("convictions", {})
                conviction = max(applied, key=applied.get) if applied else ""
                if conviction:
                    journey_lines = advance_redemption(profile, conviction)
                    if journey_lines:
                        narrative += "\n" + "\n".join(journey_lines)
            quest_lines = [
                *progress_quests(profile, "choose"),
                *progress_quests(profile, "resolve"),
                *progress_oath(profile, "choose"),
                *progress_oath(profile, "resolve"),
            ]
            if quest_lines:
                narrative += "\n\n" + "\n".join(quest_lines)
            if profile["hp"] <= 0 and profile["deaths"] == deaths_before:
                narrative += "\n\n" + self._apply_death(profile, "a fatal decision")
            profile["choice"] = {}
            if not profile["encounter"] and profile["deaths"] == deaths_before:
                profile["rooms_cleared"] += 1
            level_lines = self._apply_level_ups(profile)
            if level_lines:
                narrative += "\n\n" + "\n".join(level_lines)
            achievement_text = self._award_achievements(profile)
            if achievement_text:
                narrative += f"\n\n{achievement_text}"
            self._journal(profile, narrative.splitlines()[0].replace("*", ""))
            await self._save_profile(guild_id, user_id, profile, starting_gold)

        if profile.get("hardcore_dead"):
            await interaction.edit_original_response(
                embed=self._hardcore_death_embed(profile),
                view=None,
            )
        elif profile["encounter"]:
            await interaction.edit_original_response(
                embed=self._combat_embed(profile, narrative),
                view=CombatView(self, user_id, profile),
            )
        else:
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile, narrative),
                view=AdventureView(self, user_id),
            )

    async def _puzzle_interaction(self, interaction: discord.Interaction, answer: str) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            event = active_world_event(guild_id)
            town_bonus = float(profile.get("town_bonus", {}).get("knowledge_bonus", 0))
            result = resolve_puzzle(
                profile,
                answer,
                reward_multiplier=float(event["puzzle"]) * (1 + town_bonus),
            )
            narrative = result["message"]
            if result.get("solved"):
                quest_lines = [
                    *progress_quests(profile, "recover"),
                    *progress_oath(profile, "study"),
                ]
                if quest_lines:
                    narrative += "\n\n" + "\n".join(quest_lines)
            if profile["hp"] <= 0:
                narrative += "\n\n" + self._apply_death(profile, "an unforgiving riddle")
            profession_lines = grant_profession_xp(profile, 18 if result.get("solved") else 4)
            if profession_lines:
                narrative += "\n\n" + "\n".join(profession_lines)
            await self._save_profile(guild_id, user_id, profile, starting_gold)
        if profile.get("active_puzzle"):
            await interaction.edit_original_response(
                embed=self._puzzle_embed(profile, narrative),
                view=PuzzleView(self, user_id, profile["active_puzzle"]),
            )
        else:
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile, narrative),
                view=AdventureView(self, user_id),
            )

    async def _campaign_interaction(self, interaction: discord.Interaction, action: str | None) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            result = advance_campaign(profile, action)
            if result.get("resolved"):
                result["message"] += "\n" + "\n".join(progress_quests(profile, "decision"))
            level_lines = self._apply_level_ups(profile)
            narrative = result["message"]
            if level_lines:
                narrative += "\n\n" + "\n".join(level_lines)
            await self._save_profile(guild_id, user_id, profile, starting_gold)
        scene = campaign_scene(profile)
        view = None
        if not scene["complete"] and scene["available"]:
            if scene["at_choice"]:
                view = CampaignView(self, user_id, scene["chapter"]["choice"]["options"])
            else:
                view = CampaignContinueView(self, user_id)
        await interaction.edit_original_response(
            embed=self._campaign_embed(profile, narrative),
            view=view,
        )

    def _resolve_choice(self, profile: dict[str, Any], key: str, action: str) -> str:
        stats = self._stats(profile)
        floor = int(profile["floor"])
        if action == "leave":
            profile["reputation"] = max(0, profile["reputation"] - 1)
            return "You leave the mystery untouched. Behind you, stone grinds softly against stone."

        if key == "lastlight_camp":
            profile["camp_choices"] = int(profile.get("camp_choices", 0)) + 1
            if action == "rest":
                rate = 0.15 if profile.get("floor_mutator", {}).get("key") == "flooded" else 0.25
                healed = min(
                    stats["max_hp"] - profile["hp"],
                    max(1, round(stats["max_hp"] * rate)),
                )
                profile["hp"] += healed
                profile["status"] = {}
                profile["conviction_fatigue"] = 0
                return f"The third bedroll stays empty. You wake restored for **{healed} health**, your ailments gone."
            if action == "study":
                gained = 20 + floor * 4
                profile["xp"] += gained
                return f"The notes contain your own handwriting from years you never lived. **+{gained} XP.**"
            key_name, consumable = roll_consumable(floor)
            profile["consumables"][key_name] = int(profile["consumables"].get(key_name, 0)) + 1
            return f"Inside your own abandoned pack waits {consumable['emoji']} **{consumable['name']}**."

        if key == "judgment_mirror":
            morality = int(profile.get("morality", 0))
            if action == "absolve":
                if morality < 30:
                    damage = max(5, floor * 2)
                    profile["hp"] -= damage
                    return (
                        "The mirror finds too little mercy behind your reflection. "
                        f"Its prisoners claw through the glass for **{damage} damage**."
                    )
                healed = min(
                    stats["max_hp"] - profile["hp"],
                    max(10, round(stats["max_hp"] * 0.3)),
                )
                profile["hp"] += healed
                profile["status"] = {}
                profile["arcane_shards"] += 2
                return (
                    "The glass opens like a door. A procession of forgiven shadows passes through you, "
                    f"restoring **{healed} health**, cleansing your conditions, and leaving **2 shards**."
                )
            if action == "consume":
                if morality > -30:
                    profile["status"]["curse"] = 3
                    return "The imprisoned sins refuse an uncertain master. Their names become a **three-turn Curse**."
                shards = 3 + floor // 10
                profile["arcane_shards"] += shards
                profile["mana"] = stats["max_mana"]
                return (
                    "Your reflection opens its mouth wider than a face should allow. "
                    f"The captive sins become **{shards} shards**, and your mana is completely restored."
                )
            if not -29 <= morality <= 29:
                return "The mirror refuses compromise from a soul already claimed by certainty."
            gained = 30 + floor * 5
            profile["xp"] += gained
            profile["turns"] += 1
            return f"You and your reflection exchange one truth each. Neither is forgiven. **+{gained} XP • +1 turn.**"

        if key == "sealed_door":
            if action == "force":
                chance = min(85, 42 + stats["attack"] * 2)
                if self._passes_test(profile, chance):
                    item = self._generate_item(profile, floor + 2, stats["luck"] + 3)
                    if len(profile["inventory"]) < 25:
                        profile["inventory"].append(item)
                        return (
                            f"The final lock breaks. Inside rests **{item['rarity']} {item['name']}** — {item_stat_line(item)}."
                        )
                    gold = item_sale_value(item)
                    profile["gold"] += gold
                    return f"The relic is too large for your pack, so you recover **{self._money(profile, gold)}**."
                damage = max(5, floor * 3 - stats["defense"] // 2)
                profile["hp"] -= damage
                if profile["hp"] <= 0:
                    return f"The door's ward explodes for **{damage} damage**.\n" + self._apply_death(profile, "an ancient ward")
                return f"The ward rejects you in a flash of white fire. You suffer **{damage} damage**."
            chance = min(92, 45 + stats["luck"] * 3 + (25 if profile["class_key"] == "arcanist" else 0))
            if self._passes_test(profile, chance):
                profile["xp"] += 25 + floor * 5
                return self._discover_lore(profile)
            profile["status"]["curse"] = 3
            return "The runes read you in return. A three-turn **curse** settles over your thoughts."

        if key == "dark_altar":
            if action == "offer":
                cost = 25 + floor * 5
                if profile["gold"] < cost:
                    profile["status"]["curse"] = 2
                    return "The altar finds your offering insufficient and brands you with a **curse**."
                profile["gold"] -= cost
                profile["xp"] += 30 + floor * 6
                profile["hp"] = min(stats["max_hp"], profile["hp"] + round(stats["max_hp"] * 0.4))
                return (
                    f"The altar accepts **{self._money(profile, cost)}**. "
                    "Power floods your body, healing wounds and granting experience."
                )
            enemy = apply_affix(enemy_for_floor(floor + 1), floor + 4)
            enemy["name"] = f"Altar-Born {enemy['name']}"
            profile["combat_flags"] = {}
            profile["encounter"] = ensure_enemy_intent(enemy)
            return "The altar cracks. Something furious and half-formed crawls from the wound."

        if key == "weeping_sword":
            if action == "study":
                profile["xp"] += 35 + floor * 5
                return self._discover_lore(profile)
            chance = min(90, 38 + stats["attack"] * 2)
            if self._passes_test(profile, chance) and len(profile["inventory"]) < 25:
                item = self._generate_item(profile, floor + 3, stats["luck"] + 4, slot="weapon")
                profile["inventory"].append(item)
                return f"The stone releases its grief. You claim **{item['rarity']} {item['name']}**."
            damage = max(6, floor * 2)
            profile["hp"] -= damage
            return f"The sword refuses a stranger's hand. Its memory cuts you for **{damage} damage**."

        if key == "fungal_feast":
            if action == "aid":
                if self._passes_test(profile, 58 + stats["luck"]):
                    profile["hp"] = min(stats["max_hp"], profile["hp"] + round(stats["max_hp"] * 0.5))
                    profile["mana"] = min(stats["max_mana"], profile["mana"] + round(stats["max_mana"] * 0.5))
                    return "The feast tastes like a safe childhood. **Half your health and mana are restored.**"
                profile["status"]["poison"] = 4
                return "The mushrooms applaud inside your skull. You are **poisoned for four turns**."
            enemy = apply_affix(enemy_for_floor(floor + 1), floor + 3)
            enemy["name"] = f"Feast-Born {enemy['name']}"
            profile["combat_flags"] = {}
            profile["encounter"] = ensure_enemy_intent(enemy)
            return "Fire races across the table. The feast stands up, furious and hungry."

        if key == "clockwork_child":
            if action == "aid":
                owned = profile.setdefault("companions", {})
                newly_found = "clank" not in owned
                owned.setdefault("clank", {"level": 1, "xp": 0, "bond": 10})
                profile["active_companion"] = "clank"
                return "The key turns. Clank looks up and remembers how to smile. " + (
                    "**Clank joins you as a companion.**" if newly_found else "**Clank's bond deepens.**"
                )
            shards = 2 + floor // 5
            profile["arcane_shards"] += shards
            profile["xp"] += 30 + floor * 4
            return f"You repair its failing memory without waking it. The work yields **{shards} arcane shards**."

        if key == "empty_throne":
            if action == "offer":
                tribute = min(profile["gold"], 40 + floor * 6)
                profile["gold"] -= tribute
                profile["reputation"] += 3
                profile["xp"] += tribute
                return (
                    f"The invisible court accepts **{self._money(profile, tribute)}**. "
                    "Every ghost bows to you. **+3 reputation**."
                )
            profile["xp"] += 45 + floor * 5
            return "The throne breaks like thin ice. A thousand bound courtiers whisper their thanks."

        if key == "future_grave":
            if action == "study":
                if self._passes_test(profile, 50 + stats["luck"] * 2):
                    profile["free_revive"] = True
                    profile["turns"] += 1
                    return "You read the erased cause and choose differently. **Second Wind refreshed • +1 turn.**"
                profile["status"]["curse"] = 3
                return "The missing words write themselves across your skin. You suffer **three turns of Curse**."
            gold = 30 + floor * 8
            profile["gold"] += gold
            return f"The grave cracks. Tomorrow changes, and you find **{self._money(profile, gold)}** beneath it."

        if action == "aid":
            if profile["potions"] <= 0:
                return "You search your satchel, but have no potion to give. The delver turns away."
            profile["potions"] -= 1
            reward = 45 + floor * 7
            profile["gold"] += reward
            profile["reputation"] += 3
            return (
                "The stranger drinks and reveals themselves as a Lastlight scout. "
                f"Your kindness earns **{self._money(profile, reward)}** and **3 reputation**."
            )
        if profile["turns"] > 0:
            profile["turns"] -= 1
        profile["reputation"] += 2
        profile["potions"] += 1
        return (
            "You guide the wounded delver through a maze of listening walls. "
            "They press a potion into your hand before departing. **+2 reputation**"
        )

    async def _combat_interaction(self, interaction: discord.Interaction, action: str) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile, narrative = await self._combat_turn(interaction.guild.id, interaction.user.id, action)
        if not profile["created"]:
            await interaction.edit_original_response(embed=self._not_created_embed(), view=None)
        elif profile.get("hardcore_dead"):
            await interaction.edit_original_response(
                embed=self._hardcore_death_embed(profile),
                view=None,
            )
        elif profile["encounter"]:
            await interaction.edit_original_response(
                embed=self._combat_embed(profile, narrative),
                view=CombatView(self, interaction.user.id, profile),
            )
        else:
            await interaction.edit_original_response(
                embed=self._adventure_embed(profile, narrative),
                view=AdventureView(self, interaction.user.id),
            )

    async def _combat_turn(
        self,
        guild_id: int,
        user_id: int,
        action: str,
    ) -> tuple[dict[str, Any], str]:
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            enemy = profile.get("encounter")
            if not profile["created"] or not enemy:
                return profile, "There is nothing here to fight."

            enemy = ensure_enemy_intent(enemy)
            stats = self._stats(profile)
            legacy_effects = tenet_effects(profile)
            challenge_name = (profile.get("rift_state") or {}).get("name", "")
            if "Glass Labyrinth" in challenge_name:
                stats["attack"] = round(stats["attack"] * 1.4)
            lines: list[str] = []
            enemy_turn = True
            cast_ability_key = ""
            if (
                legacy_effects.get("blood_mana")
                and not profile["combat_flags"].get("tenet_blood_price")
                and profile["mana"] <= stats["max_mana"] - int(legacy_effects["blood_mana"])
            ):
                health_cost = max(
                    1,
                    round(stats["max_hp"] * int(legacy_effects.get("blood_cost_percent", 0)) / 100),
                )
                if profile["hp"] > health_cost:
                    profile["combat_flags"]["tenet_blood_price"] = True
                    profile["hp"] -= health_cost
                    profile["mana"] = min(
                        stats["max_mana"],
                        profile["mana"] + int(legacy_effects["blood_mana"]),
                    )
                    lines.append(f"🩸 **Blood Price** trades **{health_cost} health** for **3 mana**.")

            for condition in ("poison", "burn"):
                turns = int(enemy["status"].get(condition, 0))
                if not turns:
                    continue
                base = 4 + profile["level"]
                if condition == "poison":
                    base += int(profile.get("talents", {}).get("toxicology", 0)) * 2
                    if "origin_dirk" in equipment_effects(profile["equipment"]):
                        base += 1
                    if sum(1 for item in profile["equipment"].values() if item and item.get("set") == "widow") >= 3:
                        base = round(base * 1.25)
                elif profile.get("subclass") == "elementalist":
                    base = round(base * 1.5)
                    effects = equipment_effects(profile["equipment"])
                    if "origin_ember" in effects:
                        base += 1
                    if "heartcoal" in effects:
                        base += 2
                    if sum(1 for item in profile["equipment"].values() if item and item.get("set") == "convergence") >= 3:
                        base = round(base * 1.25)
                damage = max(1, base)
                enemy["hp"] -= damage
                enemy["status"][condition] = turns - 1
                if enemy["status"][condition] <= 0:
                    enemy["status"].pop(condition, None)
                lines.append(
                    f"{'☠️' if condition == 'poison' else '🔥'} {enemy['name']} suffers **{damage} {condition} damage**.",
                )
            if enemy["hp"] <= 0:
                enemy_turn = False
                lines.extend(self._victory(profile, enemy))

            poison_turns = int(profile.get("status", {}).get("poison", 0))
            if poison_turns:
                poison_damage = 4 + max(1, profile["floor"] // 2)
                if "venom_guard" in equipment_effects(profile["equipment"]):
                    poison_damage = max(1, round(poison_damage * 0.5))
                profile["hp"] -= poison_damage
                profile["status"]["poison"] = poison_turns - 1
                lines.append(f"☠️ Poison burns through you for **{poison_damage} damage**.")
                if profile["status"]["poison"] <= 0:
                    profile["status"].pop("poison", None)
            curse_turns = int(profile.get("status", {}).get("curse", 0))
            if curse_turns:
                stats["attack"] = max(1, round(stats["attack"] * 0.75))
                stats["luck"] = max(0, round(stats["luck"] * 0.6))
                profile["status"]["curse"] = curse_turns - 1
                if profile["status"]["curse"] <= 0:
                    profile["status"].pop("curse", None)
            if profile["hp"] <= 0:
                lines.append(self._apply_death(profile, "venom in your blood"))
                await self._save_profile(guild_id, user_id, profile, starting_gold)
                return profile, "\n".join(lines)

            if not enemy_turn:
                pass
            elif action == "conviction":
                result = use_moral_power(profile, enemy, stats)
                if not result["ok"]:
                    return profile, result["message"]
                lines.append(result["message"])
            elif action.startswith("consumable:"):
                key = action.partition(":")[2]
                consumables_before = int(profile.get("consumables", {}).get(key, 0))
                profile["_calculated_stats"] = stats
                result = use_consumable(profile, key)
                profile.pop("_calculated_stats", None)
                if not result["ok"]:
                    return profile, result["message"]
                lines.append(result["message"])
                if (
                    consumables_before > int(profile.get("consumables", {}).get(key, 0))
                    and legacy_effects.get("preserve_consumable_percent")
                    and not profile["combat_flags"].get("tenet_careful_pack")
                ):
                    profile["combat_flags"]["tenet_careful_pack"] = True
                    if random.randint(1, 100) <= int(legacy_effects["preserve_consumable_percent"]):
                        profile["consumables"][key] = int(profile["consumables"].get(key, 0)) + 1
                        lines.append("🎒 **Careful Pack** preserves the consumable.")
                if not profile.get("encounter"):
                    enemy_turn = False
            elif action == "potion":
                if "Starvation" in challenge_name:
                    return profile, "The **Starvation** modifier prevents potion use."
                if profile["potions"] <= 0:
                    return profile, "Your potion satchel is empty."
                if profile["hp"] >= stats["max_hp"]:
                    return profile, "You are already at full health."
                healing_power = round(
                    (35 + profile["level"] * 5) * (1 + float(profile.get("town_bonus", {}).get("potion_bonus", 0))),
                )
                healing = min(stats["max_hp"] - profile["hp"], healing_power)
                profile["potions"] -= 1
                profile["hp"] += healing
                lines.append(f"🧪 You recover **{healing} health**.")
                if (
                    legacy_effects.get("first_potion_mana")
                    and not profile["combat_flags"].get("tenet_first_potion")
                ):
                    profile["combat_flags"]["tenet_first_potion"] = True
                    restored = min(
                        stats["max_mana"] - profile["mana"],
                        int(legacy_effects["first_potion_mana"]),
                    )
                    profile["mana"] += restored
                    if restored:
                        lines.append(f"◆ **Mercy Repaid** restores **{restored} mana**.")
                if "mercy" in equipment_effects(profile["equipment"]):
                    profile["combat_flags"]["guard"] = max(
                        float(profile["combat_flags"].get("guard", 0)),
                        0.18,
                    )
                    lines.append("🤍 Mercy's sigil grants **18% guard** against the next attack.")
            elif action == "flee":
                penalty = 20 if "Fool's Gold" in challenge_name else 0
                if profile.get("floor_mutator", {}).get("key") == "darkness":
                    penalty += 12
                flee_chance = min(
                    82,
                    42 + stats["luck"] * 3 - (12 if enemy.get("boss") else 0) - penalty,
                )
                if random.randint(1, 100) <= flee_chance:
                    profile["encounter"] = {}
                    if restore_challenge_origin(profile):
                        lines.append("🌀 The challenge collapses, returning you to your original expedition.")
                    else:
                        profile["rooms_cleared"] += 1
                    enemy_turn = False
                    lines.append("💨 You escape through a narrow passage. Pride is cheaper than a funeral.")
                else:
                    lines.append("💨 Your escape route is cut off!")
            elif action == "defend":
                guard = 0.55 + min(0.2, stats["defense"] * 0.008)
                if profile["hp"] <= stats["max_hp"] / 2:
                    guard += float(legacy_effects.get("guard_bonus", 0))
                effects = equipment_effects(profile["equipment"])
                if "origin_frost" in effects:
                    guard = min(0.82, guard + 0.05)
                profile["combat_flags"]["guard"] = guard
                retaliation_rank = int(profile.get("talents", {}).get("retaliation", 0))
                if retaliation_rank:
                    profile["combat_flags"]["retaliate"] = max(
                        1,
                        round(stats["defense"] * retaliation_rank * 0.18),
                    )
                if "origin_bastion" in effects or "thorns" in effects:
                    profile["combat_flags"]["retaliate"] = max(
                        int(profile["combat_flags"].get("retaliate", 0)),
                        max(2, round(stats["defense"] * 0.2)),
                    )
                healing_percent = (
                    0.03
                    if sum(1 for item in profile["equipment"].values() if item and item.get("set") == "citadel") >= 3
                    else 0.02
                    if "brace" in effects
                    else 0
                )
                if healing_percent:
                    healed = min(
                        stats["max_hp"] - profile["hp"],
                        max(1, round(stats["max_hp"] * healing_percent)),
                    )
                    profile["hp"] += healed
                    if healed:
                        lines.append(f"💚 Your equipment restores **{healed} health**.")
                mana_recovery = 1 if profile.get("floor_mutator", {}).get("key") == "hollow" else 2
                defend_count = int(profile["combat_flags"].get("tenet_defend_count", 0)) + 1
                profile["combat_flags"]["tenet_defend_count"] = defend_count
                cycle = int(legacy_effects.get("defend_mana_cycle", 0))
                if cycle and defend_count % cycle == 0:
                    mana_recovery += 1
                profile["mana"] = min(stats["max_mana"], profile["mana"] + mana_recovery)
                profile["combat_flags"]["tenet_last_action"] = "defend"
                lines.append(
                    f"🛡️ You brace for **{round(guard * 100)}% damage reduction** and recover **{mana_recovery} mana**.",
                )
            elif action.startswith("ability:"):
                ability_key = action.partition(":")[2]
                ability = next(
                    (entry for entry in available_abilities(profile) if entry["key"] == ability_key),
                    None,
                )
                if not ability:
                    return profile, "That ability is not unlocked."
                if profile["skill_cooldowns"].get(ability_key, 0):
                    return profile, (
                        f"**{ability['name']}** is cooling down for {profile['skill_cooldowns'][ability_key]} more turn(s)."
                    )
                set_counts: dict[str, int] = {}
                for equipped in profile["equipment"].values():
                    if equipped and equipped.get("set"):
                        set_counts[equipped["set"]] = set_counts.get(equipped["set"], 0) + 1
                starweaver_free = set_counts.get("starweaver", 0) >= 3 and (profile["ability_casts"] + 1) % 3 == 0
                mana_cost = 0 if starweaver_free else ability["mana"]
                equipped_effects = equipment_effects(profile["equipment"])
                if "origin_hourglass" in equipped_effects and not profile["combat_flags"].get("origin_hourglass_used"):
                    mana_cost = max(0, mana_cost - 1)
                    profile["combat_flags"]["origin_hourglass_used"] = True
                if profile["mana"] < mana_cost:
                    return profile, f"You need **{ability['mana']} mana** to use {ability['name']}."
                profile["mana"] -= mana_cost
                profile["ability_casts"] += 1
                cast_ability_key = ability_key
                damage, skill_lines = self._ability_damage(
                    profile,
                    enemy,
                    stats,
                    ability_key,
                )
                if (
                    profile["combat_flags"].get("tenet_last_action") == "defend"
                    and legacy_effects.get("post_defend_damage_percent")
                ):
                    damage = round(damage * (1 + int(legacy_effects["post_defend_damage_percent"]) / 100))
                    skill_lines.append("🐺 **Predator's Patience** turns defense into force.")
                if (
                    enemy.get("boss")
                    and enemy["hp"] <= enemy["max_hp"] * 0.3
                    and legacy_effects.get("execute_percent")
                ):
                    damage = round(damage * (1 + int(legacy_effects["execute_percent"]) / 100))
                    skill_lines.append("🕯️ **Last Lantern** burns brighter at the brink.")
                if profile.get("floor_mutator", {}).get("key") == "unstable":
                    volatility = random.uniform(0.9, 1.15)
                    damage = max(1, round(damage * volatility))
                    skill_lines.append(
                        f"🌀 Unstable magic shifts the spell to **{round(volatility * 100)}% potency**.",
                    )
                overchannel = (
                    profile["class_key"] == "arcanist" and profile["talents"].get("overchannel", 0) and random.random() < 0.2
                )
                if not overchannel:
                    profile["skill_cooldowns"][ability_key] = ability["cooldown"]
                else:
                    skill_lines.append("🌌 **Overchannel** prevents the ability from entering cooldown.")
                if starweaver_free:
                    skill_lines.append("🌠 **Starweaver** makes the ability cost no mana.")
                if "echoes" in equipped_effects and random.random() < 0.25:
                    profile["mana"] = min(stats["max_mana"], profile["mana"] + 1)
                    skill_lines.append("🔊 An echo refunds **1 mana**.")
                if "clock_key" in equipped_effects and profile["ability_casts"] % 3 == 0:
                    profile["mana"] = min(stats["max_mana"], profile["mana"] + 2)
                    skill_lines.append("🗝️ Key to Yesterday refunds **2 mana**.")
                if set_counts.get("paradox", 0) >= 3 and profile["ability_casts"] % 4 == 0 and profile["skill_cooldowns"]:
                    alternatives = [key for key in profile["skill_cooldowns"] if key != ability_key]
                    if alternatives:
                        paradox_key = random.choice(alternatives)
                        profile["skill_cooldowns"][paradox_key] = max(
                            0,
                            int(profile["skill_cooldowns"][paradox_key]) - 1,
                        )
                        skill_lines.append("🌀 Paradox Regalia advances another cooldown.")
                enemy["hp"] -= damage
                profile["combat_flags"]["tenet_last_action"] = "ability"
                lines.extend(skill_lines)
            else:
                previous_action = profile["combat_flags"].get("tenet_last_action")
                if profile["combat_flags"].pop("next_crit", False):
                    stats["luck"] += 30
                defense = int(enemy["defense"])
                effects = equipment_effects(profile["equipment"])
                if "origin_handbow" in effects:
                    defense = round(defense * 0.9)
                damage, critical = self._player_damage(stats, defense)
                if "origin_spear" in effects and not profile["combat_flags"].get("origin_spear_used"):
                    damage = round(damage * 1.12)
                    profile["combat_flags"]["origin_spear_used"] = True
                if "venom_burst" in effects and enemy.get("status", {}).get("poison"):
                    damage = round(damage * 1.12)
                if "hunger" in effects and profile["hp"] <= stats["max_hp"] * 0.35:
                    damage = round(damage * 1.12)
                if "ruin" in effects:
                    enemy["defense"] = max(0, enemy["defense"] - 1)
                if "revision" in effects and not profile["combat_flags"].get("revision_used"):
                    enemy["intent"] = roll_enemy_intent(enemy)
                    profile["combat_flags"]["revision_used"] = True
                    lines.append("🖋️ **Red Revision** rewrites the enemy's intention.")
                if "battle_mana" in effects and not profile["combat_flags"].get("battle_mana_used"):
                    profile["mana"] = min(stats["max_mana"], profile["mana"] + 2)
                    profile["combat_flags"]["battle_mana_used"] = True
                    lines.append("🔊 Echoing Fang restores **2 mana**.")
                if not profile.get("status") and not enemy.get("status") and legacy_effects.get("clean_attack_percent"):
                    damage = round(damage * (1 + int(legacy_effects["clean_attack_percent"]) / 100))
                    lines.append("⚖️ **Even Edge** rewards the uncontested exchange.")
                if previous_action == "defend" and legacy_effects.get("post_defend_damage_percent"):
                    damage = round(damage * (1 + int(legacy_effects["post_defend_damage_percent"]) / 100))
                    lines.append("🐺 **Predator's Patience** turns defense into force.")
                if (
                    enemy.get("boss")
                    and enemy["hp"] <= enemy["max_hp"] * 0.3
                    and legacy_effects.get("execute_percent")
                ):
                    damage = round(damage * (1 + int(legacy_effects["execute_percent"]) / 100))
                    lines.append("🕯️ **Last Lantern** burns brighter at the brink.")
                if previous_action == "ability" and legacy_effects.get("alternating_guard"):
                    profile["combat_flags"]["guard"] = max(
                        float(profile["combat_flags"].get("guard", 0)),
                        float(legacy_effects["alternating_guard"]),
                    )
                    lines.append("⚖️ **Balanced Guard** covers the change in rhythm.")
                if enemy.get("guarded", 0):
                    damage = max(1, round(damage * 0.5))
                    enemy["guarded"] = 0
                    lines.append("🛡️ The enemy's defensive stance absorbs half the blow.")
                enemy["hp"] -= damage
                profile["combat_flags"]["tenet_last_action"] = "basic"
                prefix = "💥 **CRITICAL!** " if critical else "⚔️ "
                lines.append(f"{prefix}You deal **{damage} damage**.")
                if critical:
                    self._apply_item_critical_effects(profile, enemy, lines)
                    if profile["talents"].get("opportunist", 0) and profile["skill_cooldowns"]:
                        cooldown_key = random.choice(list(profile["skill_cooldowns"]))
                        profile["skill_cooldowns"][cooldown_key] = max(
                            0,
                            profile["skill_cooldowns"][cooldown_key] - 1,
                        )

            if enemy and enemy.get("hp", 0) <= 0:
                enemy_turn = False
                lines.extend(self._victory(profile, enemy))

            if enemy_turn and profile["encounter"]:
                lines.extend(self._resolve_enemy_intent(profile, enemy, stats))
                if enemy["hp"] <= 0 and profile["hp"] > 0:
                    lines.extend(self._victory(profile, enemy))
                if enemy.get("weakened", 0):
                    enemy["weakened"] = max(0, int(enemy["weakened"]) - 1)
                if profile["hp"] <= 0:
                    lines.append(self._apply_death(profile, enemy["name"]))

            pending_first = profile.pop("pending_server_first", "")
            if pending_first:
                firsts = await self.config.guild_from_id(guild_id).server_firsts()
                if pending_first not in firsts:
                    firsts[pending_first] = {
                        "user_id": user_id,
                        "date": datetime.now(timezone.utc).isoformat(),
                    }
                    await self.config.guild_from_id(guild_id).server_firsts.set(firsts)
                    lines.append(
                        f"📣 **SERVER FIRST!** <@{user_id}> is the first delver to defeat **{pending_first}**.",
                    )

            achievement_text = self._award_achievements(profile)
            if achievement_text:
                lines.append(achievement_text)
            self._advance_cooldowns(profile, exclude=cast_ability_key)
            await self._save_profile(guild_id, user_id, profile, starting_gold)
            return profile, "\n".join(lines)

    @staticmethod
    def _advance_cooldowns(profile: dict[str, Any], *, exclude: str = "") -> None:
        """Advance cooldowns after a completed action, excluding the ability just cast."""
        reduction = 2 if profile.get("subclass") == "chronomancer" else 1
        for ability_key, remaining in list(profile.get("skill_cooldowns", {}).items()):
            if ability_key == exclude:
                continue
            remaining = int(remaining) - reduction
            if remaining <= 0:
                profile["skill_cooldowns"].pop(ability_key, None)
            else:
                profile["skill_cooldowns"][ability_key] = remaining

    @staticmethod
    def _player_damage(stats: dict[str, int], enemy_defense: int) -> tuple[int, bool]:
        critical_chance = min(55, 5 + stats["luck"] * 2 + stats.get("critical_bonus", 0))
        critical = random.randint(1, 100) <= critical_chance
        base = random.randint(max(1, stats["attack"] - 3), stats["attack"] + 4)
        damage = max(1, base - enemy_defense // 2)
        if critical:
            damage = round(damage * 1.75)
        return damage, critical

    def _skill_damage(
        self,
        profile: dict[str, Any],
        enemy: dict[str, Any],
        stats: dict[str, int],
    ) -> tuple[int, list[str]]:
        class_key = profile["class_key"]
        if class_key == "vanguard":
            base, critical = self._player_damage(stats, int(enemy["defense"]))
            damage = round(base * 1.4)
            enemy["weakened"] = 2
            return damage, [
                f"🛡️ **Shield Bash** crashes home for **{damage} damage**{'—a critical blow!' if critical else '!'}",
                "The enemy is weakened for its next attack.",
            ]
        if class_key == "shadow":
            total = 0
            criticals = 0
            boosted = dict(stats)
            boosted["luck"] += 7
            for _ in range(2):
                damage, critical = self._player_damage(boosted, int(enemy["defense"]))
                total += max(1, round(damage * 0.72))
                criticals += int(critical)
            return total, [
                f"🗡️ **Twin Fang** strikes twice for **{total} total damage** "
                f"with **{criticals} critical hit{'s' if criticals != 1 else ''}.",
            ]
        base = random.randint(stats["attack"] + 3, stats["attack"] + 10)
        damage = max(1, round(base * 1.55) - int(enemy["defense"]) // 6)
        return damage, [f"🔮 **Arcane Lance** tears through armor for **{damage} damage**."]

    def _ability_damage(
        self,
        profile: dict[str, Any],
        enemy: dict[str, Any],
        stats: dict[str, int],
        ability_key: str,
    ) -> tuple[int, list[str]]:
        if ability_key in {"shield_bash", "twin_fang", "arcane_lance"}:
            damage, lines = self._skill_damage(profile, enemy, stats)
            if ability_key == "shield_bash" and "origin_maul" in equipment_effects(profile["equipment"]):
                bonus = max(1, round(damage * 0.08))
                damage += bonus
                lines.append(f"🔨 Ashen Maul adds **{bonus} damage**.")
        elif ability_key == "iron_wall":
            profile["combat_flags"]["guard"] = 0.82
            profile["combat_flags"]["retaliate"] = max(3, stats["defense"])
            damage, lines = 0, ["🏰 **Iron Wall** locks into place. The next attack will be crushed."]
        elif ability_key == "sunder":
            damage = max(1, round(stats["attack"] * 1.35) - enemy["defense"] // 3)
            removed = max(1, round(enemy["defense"] * 0.3))
            enemy["defense"] = max(0, enemy["defense"] - removed)
            lines = [f"🔨 **Sunder** deals **{damage} damage** and destroys **{removed} armor**."]
        elif ability_key == "last_stand":
            missing = max(0, stats["max_hp"] - profile["hp"])
            healed = min(missing, round(stats["max_hp"] * 0.3))
            profile["hp"] += healed
            profile["combat_flags"]["guard"] = 0.5
            damage = max(1, round(stats["attack"] * (1.15 + missing / stats["max_hp"] * 0.8)))
            lines = [
                f"🚩 **Last Stand** restores **{healed} health** and deals **{damage} damage**.",
            ]
        elif ability_key == "venom_edge":
            damage = max(1, round(stats["attack"] * 1.15) - enemy["defense"] // 3)
            enemy["status"]["poison"] = max(enemy["status"].get("poison", 0), 4)
            lines = [f"☠️ **Venom Edge** deals **{damage} damage** and inflicts Poison."]
        elif ability_key == "smoke_bomb":
            profile["combat_flags"]["evade"] = True
            profile["combat_flags"]["next_crit"] = True
            damage, lines = 0, ["💨 **Smoke Bomb** guarantees an evasion and empowers your next critical."]
        elif ability_key == "execution":
            multiplier = 2.75 if enemy["hp"] <= enemy["max_hp"] / 2 else 1.25
            damage = max(1, round(stats["attack"] * multiplier) - enemy["defense"] // 2)
            lines = [f"🦂 **Execution** strikes for **{damage} damage**."]
        elif ability_key == "frost_ward":
            profile["combat_flags"]["guard"] = 0.7
            enemy["weakened"] = max(enemy.get("weakened", 0), 2)
            damage, lines = 0, ["❄️ **Frost Ward** shields you and weakens the enemy."]
        elif ability_key == "starfire":
            damage = max(1, round(stats["attack"] * 1.75) - enemy["defense"] // 5)
            enemy["status"]["burn"] = max(enemy["status"].get("burn", 0), 4)
            lines = [f"🔥 **Starfire** erupts for **{damage} damage** and ignites the enemy."]
        else:
            damage = max(1, round(stats["attack"] * 1.45) - enemy["defense"] // 5)
            enemy["intent"] = roll_enemy_intent(enemy)
            for key in list(profile["skill_cooldowns"]):
                profile["skill_cooldowns"][key] = max(0, profile["skill_cooldowns"][key] - 2)
            lines = [
                f"⏳ **Time Fracture** deals **{damage} damage**, cancels the intention, and advances your cooldowns.",
            ]
        ability_bonus = stats.get("ability_percent", 0)
        if profile.get("subclass") == "assassin" and enemy.get("status", {}).get("poison") and damage:
            bonus = round(damage * 0.2)
            damage += bonus
            lines.append(f"🦂 Deathmark adds **{bonus} damage** against the poisoned target.")
        if damage and ability_bonus:
            bonus = round(damage * ability_bonus / 100)
            damage += bonus
            lines.append(f"🌌 Spellpower adds **{bonus} damage**.")
        if enemy.get("guarded", 0) and damage:
            damage = max(1, round(damage * 0.5))
            enemy["guarded"] = 0
            lines.append("🛡️ The enemy's guard absorbs half the ability's damage.")
        if damage and profile.get("class_key") == "vanguard" and (enemy.get("boss") or enemy.get("miniboss")):
            bonus = max(1, round(damage * 0.18))
            damage += bonus
            lines.append(f"🛡️ Vanguard armor-breaking adds **{bonus} damage** against the champion.")
        return damage, lines

    @staticmethod
    def _apply_item_critical_effects(
        profile: dict[str, Any],
        enemy: dict[str, Any],
        lines: list[str],
    ) -> None:
        effects = equipment_effects(profile.get("equipment", {}))
        nightstalker = sum(1 for item in profile.get("equipment", {}).values() if item and item.get("set") == "nightstalker")
        duration = 4 if nightstalker >= 3 else 3
        if "burn" in effects and random.random() < 0.35:
            enemy["status"]["burn"] = max(enemy["status"].get("burn", 0), duration)
            lines.append("🔥 Your equipment ignites the target.")
        if "poison" in effects and random.random() < 0.35:
            enemy["status"]["poison"] = max(enemy["status"].get("poison", 0), duration)
            lines.append("☠️ Your equipment poisons the target.")
        if "silence" in effects and random.random() < 0.25:
            enemy["intent"] = roll_enemy_intent(enemy)
            lines.append("🔕 Bellower's Silence disrupts the enemy's intention.")
        if "cinderstrike" in effects:
            enemy["status"]["burn"] = max(enemy["status"].get("burn", 0), 3)
            lines.append("🔥 Embermaw's Tooth ignites the target.")
        if {"quickening", "hourbreaker"} & effects and profile["skill_cooldowns"]:
            chance = 0.45 if "hourbreaker" in effects else 0.25
            if random.random() < chance:
                key = random.choice(list(profile["skill_cooldowns"]))
                profile["skill_cooldowns"][key] = max(0, profile["skill_cooldowns"][key] - 1)
                lines.append("⏳ Your critical advances a cooldown.")

    def _resolve_enemy_intent(
        self,
        profile: dict[str, Any],
        enemy: dict[str, Any],
        stats: dict[str, int],
    ) -> list[str]:
        intent = ensure_enemy_intent(enemy)["intent"]
        lines: list[str] = []
        if enemy.get("boss"):
            ratio = enemy["hp"] / max(1, enemy["max_hp"])
            phase = int(enemy.get("phase", 1))
            next_phase = 3 if ratio <= 0.33 else 2 if ratio <= 0.66 else 1
            if next_phase > phase:
                enemy["phase"] = next_phase
                enemy["attack"] = round(enemy["attack"] * (1.1 if next_phase == 3 else 1.08))
                enemy["intent"] = roll_enemy_intent(enemy)
                intent = enemy["intent"]
                lines.append(
                    f"👑 **BOSS PHASE {next_phase}** — {enemy['name']} changes tactics and grows more dangerous.",
                )
        equipped_effects = equipment_effects(profile.get("equipment", {}))
        if profile["combat_flags"].pop("reroll_intent", False):
            enemy["intent"] = roll_enemy_intent(enemy)
            intent = enemy["intent"]
            lines.append("🪞 The enemy's intention is rewritten.")
        if "web" in equipped_effects and not profile["combat_flags"].get("web_used"):
            profile["combat_flags"]["web_used"] = True
            lines.append("🕸️ **Arachne's Promise** entangles the first incoming attack.")
            enemy["intent"] = roll_enemy_intent(enemy)
            return lines
        if profile["combat_flags"].pop("evade", False):
            lines.append(f"💨 You evade **{intent['name']}** completely.")
            enemy["intent"] = roll_enemy_intent(enemy)
            return lines
        evasion_rank = int(profile.get("talents", {}).get("evasion", 0))
        if evasion_rank and random.random() < evasion_rank * 0.06:
            lines.append(f"🃏 **Evasion** avoids {intent['name']}.")
            enemy["intent"] = roll_enemy_intent(enemy)
            return lines
        if "saint_veil" in equipped_effects and random.random() < 0.06:
            lines.append("🌑 The Saint's Veil erases you from the attack.")
            enemy["intent"] = roll_enemy_intent(enemy)
            return lines
        mirrorsteel = sum(1 for item in profile["equipment"].values() if item and item.get("set") == "mirrorsteel")
        riposte_chance = 0.2 if mirrorsteel >= 3 else 0.12
        if profile.get("subclass") == "duelist" and random.random() < riposte_chance:
            counter = max(1, round(stats["attack"] * 0.7))
            enemy["hp"] -= counter
            lines.append(f"🤺 **Riposte** avoids the attack and counters for **{counter} damage**.")
            enemy["intent"] = roll_enemy_intent(enemy)
            return lines

        hits = int(intent.get("hits", 1))
        total = 0
        for _ in range(hits):
            base_damage = self._enemy_damage(enemy, stats)
            total += max(1, round(base_damage * float(intent["power"])))
        if intent["key"] == "heavy" and "resonance" in equipped_effects:
            total = round(total * 0.85)
        if intent["key"] == "heavy" and "stasis" in equipped_effects and not profile["combat_flags"].get("stasis_used"):
            total = round(total * 0.65)
            profile["combat_flags"]["stasis_used"] = True
            lines.append("⏳ Armor of the Held Moment catches the crushing blow.")
        if "warding" in equipped_effects and enemy.get("affix"):
            total = round(total * 0.85)
        if profile.get("status", {}).pop("vulnerable", 0):
            total = round(total * 1.1)
            lines.append("🩸 Borrowed Vigor leaves you vulnerable to this attack.")
        guard = float(profile["combat_flags"].pop("guard", 0))
        if guard:
            prevented = round(total * guard)
            total -= prevented
            lines.append(f"🛡️ Your guard prevents **{prevented} damage**.")
        mana_shield = int(profile.get("talents", {}).get("mana_shield", 0))
        if mana_shield and profile["mana"] and total:
            absorbed = min(profile["mana"], round(total * mana_shield * 0.1))
            profile["mana"] -= absorbed
            total -= absorbed
            lines.append(f"🔷 Mana Shield absorbs **{absorbed} damage**.")
        profile["hp"] -= max(0, total)
        lines.append(
            f"{intent['emoji']} **{enemy['name']} uses {intent['name']}** for **{max(0, total)} damage**.",
        )
        heavy_guard = tenet_effects(profile).get("heavy_revenge_guard", 0)
        if intent["key"] == "heavy" and heavy_guard:
            profile["combat_flags"]["guard"] = max(
                float(profile["combat_flags"].get("guard", 0)),
                float(heavy_guard),
            )
            lines.append("🌑 **Unyielding Claim** guards against the next attack.")

        retaliation = int(profile["combat_flags"].pop("retaliate", 0))
        if retaliation:
            bulwark_count = sum(1 for item in profile.get("equipment", {}).values() if item and item.get("set") == "bulwark")
            if profile.get("subclass") == "guardian" or bulwark_count >= 3:
                retaliation *= 2
            enemy["hp"] -= retaliation
            lines.append(f"🛡️ You retaliate for **{retaliation} damage**.")
        if intent["key"] == "guard":
            enemy["guarded"] = 1
            lines.append("🛡️ The enemy gains a defensive stance.")
        elif intent["key"] == "hex" and random.random() < 0.55:
            profile["status"]["curse"] = max(profile["status"].get("curse", 0), 3)
            lines.append("🕸️ The hex inflicts **Curse**.")
        elif intent["key"] == "recover":
            healing = max(1, round(enemy["max_hp"] * 0.08))
            enemy["hp"] = min(enemy["max_hp"], enemy["hp"] + healing)
            lines.append(f"🩸 The enemy restores **{healing} health**.")

        affix_effect = (enemy.get("affix") or {}).get("effect")
        if affix_effect == "poison" and random.random() < 0.35:
            profile["status"]["poison"] = max(profile["status"].get("poison", 0), 3)
            lines.append("☠️ Venom enters the wound. You are **poisoned for three turns**.")
        elif affix_effect == "drain" and total:
            healing = max(1, total // 2)
            enemy["hp"] = min(enemy["max_hp"], enemy["hp"] + healing)
            lines.append(f"🩸 The creature drains your life and restores **{healing} health**.")
        enemy["intent"] = roll_enemy_intent(enemy)
        return lines

    @staticmethod
    def _enemy_damage(enemy: dict[str, Any], stats: dict[str, int]) -> int:
        attack = round(int(enemy["attack"]) * float(enemy.get("threat_multiplier", 1.0)))
        if enemy.get("weakened", 0):
            attack = round(attack * 0.68)
        base = random.randint(max(1, attack - 2), attack + 3)
        defense_rate = 0.26 if enemy.get("boss") else 0.44
        blocked = min(round(base * 0.62), round(stats["defense"] * defense_rate))
        return max(1, base - blocked)

    def _victory(self, profile: dict[str, Any], enemy: dict[str, Any]) -> list[str]:
        event_reward = float(enemy.get("event_reward", 1.0))
        if profile.get("combat_flags", {}).pop("tenet_death_save_penalty", False):
            event_reward *= 0.9
        gold = round(int(enemy["gold"]) * event_reward)
        equipped_effects = equipment_effects(profile.get("equipment", {}))
        if "fortune" in equipped_effects:
            gold = round(gold * 1.12)
        if enemy.get("boss") and "royal_fortune" in equipped_effects:
            gold = round(gold * 1.12)
        gold = round(
            gold * (1 + int(profile.get("guild_bonus", {}).get("currency_percent", 0)) / 100),
        )
        xp = round(int(enemy["xp"]) * event_reward)
        profile["gold"] += gold
        profile["xp"] += xp
        profile["kills"] += 1
        profile["rooms_cleared"] += 1
        atlas_lines = record_dungeon_victory(profile, enemy)
        profile["encounter"] = {}
        if enemy.get("boss"):
            profile["bosses"] += 1
            profile["pending_server_first"] = enemy["name"]
        self._journal(profile, f"Defeated {enemy['name']} and claimed {self._money(profile, gold)}.")
        lines = [
            f"🏆 **{enemy['name']} is defeated!**",
            f"You gain **{xp} XP** and **{self._money(profile, gold)}**.",
        ]
        lines.extend(atlas_lines)
        lines.extend(progress_quests(profile, "defeat"))
        lines.extend(progress_oath(profile, "defeat"))
        lines.extend(progress_oath(profile, "hunt"))
        lines.extend(progress_commission(profile, "defeat"))
        if enemy.get("boss"):
            granted = grant_resolve(profile, 1, f"boss:{enemy.get('name')}:{enemy.get('floor', profile['floor'])}")
            if granted:
                lines.append("◆ A unique boss decision hardens into **1 Resolve**.")
        if enemy.get("nemesis_id"):
            defeated, message = defeat_nemesis(profile, int(enemy["nemesis_id"]))
            if defeated:
                lines.append(message)
        borrowed_vigor = tenet_effects(profile).get("elite_heal_percent", 0)
        if enemy.get("affix") and borrowed_vigor:
            stats_now = self._stats(profile)
            healed = min(
                stats_now["max_hp"] - profile["hp"],
                max(1, round(stats_now["max_hp"] * int(borrowed_vigor) / 100)),
            )
            profile["hp"] += healed
            profile.setdefault("status", {})["vulnerable"] = 1
            lines.append(f"🩸 **Borrowed Vigor** restores **{healed} health**, but leaves one vulnerable turn.")
        if enemy.get("boss"):
            if profile.get("conviction_fatigue", 0):
                lines.append("⚖️ Defeating a boss clears all **Conviction Fatigue**.")
            profile["conviction_fatigue"] = 0
        elif (
            int(profile.get("conviction_fatigue", 0)) > 0
            and not profile.get("combat_flags", {}).get("moral_power_used")
        ):
            profile["conviction_fatigue"] -= 1
            if profile["conviction_fatigue"] == 0:
                lines.append("⚖️ Your Conviction power is ready again.")
        if not enemy.get("boss"):
            stats_now = self._stats(profile)
            restored = min(
                stats_now["max_mana"] - profile["mana"],
                max(1, round(stats_now["max_mana"] * 0.04)),
            )
            profile["mana"] += restored
            if restored:
                lines.append(f"🔷 Battle focus restores **{restored} mana**.")
        companion_lines = grant_companion_xp(profile, max(5, xp // 5))
        if companion_lines:
            lines.extend(companion_lines)
        profession_lines = grant_profession_xp(profile, 8 if enemy.get("boss") else 3)
        if profession_lines:
            lines.extend(profession_lines)
        grave_covenant = sum(1 for item in profile["equipment"].values() if item and item.get("set") == "grave_covenant")
        if "mending" in equipped_effects or profile.get("subclass") == "necromancer":
            stats_now = self._stats(profile)
            healing_rate = 0.12 if grave_covenant >= 3 else 0.08
            healing = min(
                stats_now["max_hp"] - profile["hp"],
                max(3, round(stats_now["max_hp"] * healing_rate)),
            )
            profile["hp"] += healing
            if healing:
                lines.append(f"💚 Soul energy restores **{healing} health**.")
        if enemy.get("boss") and "soulrend" in equipped_effects:
            stats_now = self._stats(profile)
            healing = min(
                stats_now["max_hp"] - profile["hp"],
                max(4, round(stats_now["max_hp"] * 0.1)),
            )
            profile["hp"] += healing
            if healing:
                lines.append(f"🗡️ Kingslayer drinks the fallen crown and restores **{healing} health**.")

        stats = self._stats(profile)
        rook_bonus = min(10, int(profile["npc_reputation"].get("rook", 0)) // 2)
        drop_chance = min(
            90,
            20 + stats["luck"] * 2 + rook_bonus + (35 if enemy.get("boss") else 0) + int(profile.get("loot_pity", 0)),
        )
        if sum(1 for item in profile["equipment"].values() if item and item.get("set") == "loaded_fate") >= 3:
            drop_chance = min(92, drop_chance + 8)
        if profile.get("profession", {}).get("key") == "relic_hunter":
            drop_chance = min(90, drop_chance + 5 + int(profile["profession"].get("level", 1)))
        if random.randint(1, 100) <= drop_chance:
            profile["loot_pity"] = 0
            item = None
            if enemy.get("boss"):
                pity = int(profile.get("boss_relic_pity", 0))
                if pity >= 4 or random.random() < 0.22:
                    item = boss_relic_for(enemy["name"], profile["floor"] + 3)
                    if item:
                        profile["boss_relic_pity"] = 0
                else:
                    profile["boss_relic_pity"] = pity + 1
            if not item:
                item = self._generate_item(
                    profile,
                    profile["floor"] + (3 if enemy.get("boss") else 0),
                    stats["luck"] + (5 if enemy.get("boss") else 0),
                )
            lines.append(self._store_loot(profile, item))
        else:
            profile["loot_pity"] = min(18, int(profile.get("loot_pity", 0)) + 3)
            if enemy.get("boss"):
                profile["boss_relic_pity"] = min(
                    4,
                    int(profile.get("boss_relic_pity", 0)) + 1,
                )

        consumable_chance = 0.4 if enemy.get("boss") else 0.3 if enemy.get("miniboss") else 0.12
        if random.random() < consumable_chance:
            consumable_key, consumable = roll_consumable(int(enemy.get("floor", profile["floor"])))
            profile["consumables"][consumable_key] = int(profile["consumables"].get(consumable_key, 0)) + 1
            lines.append(f"{consumable['emoji']} Supply: **{consumable['name']}** — {consumable['description']}")

        lines.extend(record_bestiary_kill(profile, enemy))
        lines.extend(progress_rumor(profile, enemy))

        level_lines = self._apply_level_ups(profile)
        lines.extend(level_lines)
        if enemy.get("boss"):
            profile.setdefault("run_history", []).append(
                {
                    "boss": enemy["name"],
                    "floor": int(enemy.get("floor", profile["floor"])),
                    "level": profile["level"],
                    "alignment": profile.get("alignment", "Pragmatic"),
                },
            )
            profile["run_history"] = profile["run_history"][-20:]
            profile["floor"] += 1
            profile["rooms_cleared"] = 0
            profile["deepest_floor"] = max(profile["deepest_floor"], profile["floor"])
            profile["floor_mutator"] = floor_mutator(profile["floor"], profile.get("ascensions", 0))
            profile["hp"] = min(self._stats(profile)["max_hp"], profile["hp"] + 30)
            profile["mana"] = min(self._stats(profile)["max_mana"], profile["mana"] + 15)
            lines.append(f"🔓 The sealed stair opens. **Floor {profile['floor']}** awaits.")
            for key in unlock_companions(profile):
                companion = COMPANIONS[key]
                lines.append(
                    f"{companion['emoji']} **Companion discovered: {companion['name']}!** "
                    f"{companion['description']} Recruit them in `/deepdelve chronicle companion`.",
                )

        region = region_for_floor(enemy.get("floor", profile["floor"]))
        material_key = region["material"]
        material_chance = 0.9 if enemy.get("boss") else 0.55
        if random.random() <= material_chance:
            amount = random.randint(2, 4) if enemy.get("boss") else 1
            profile["materials"][material_key] = profile["materials"].get(material_key, 0) + amount
            material = MATERIALS[material_key]
            lines.append(f"{material['emoji']} You recover **{amount} {material['name']}**.")
        if profile.get("profession", {}).get("key") == "relic_hunter":
            level = int(profile["profession"].get("level", 1))
            if random.random() < min(0.55, 0.15 + level * 0.015):
                shards = 2 if enemy.get("boss") else 1
                profile["arcane_shards"] += shards
                lines.append(f"🏺 Relic Hunter insight reveals **{shards} arcane shard(s)**.")
        active = active_companion(profile)
        if active:
            companion, progress = active
            if profile.get("active_companion") == "mote":
                restored = min(
                    self._stats(profile)["max_mana"] - profile["mana"],
                    min(5, 2 + int(progress.get("level", 1)) // 4),
                )
                profile["mana"] += restored
                if restored:
                    lines.append(f"{companion['emoji']} Mote restores **{restored} mana**.")
            elif profile.get("active_companion") == "clank" and random.random() < 0.22:
                profile["materials"][material_key] += 1
                lines.append(f"{companion['emoji']} Clank salvages **1 extra {MATERIALS[material_key]['name']}**.")
            elif profile.get("active_companion") == "echo" and random.random() < 0.12:
                profile["turns"] += 1
                lines.append(f"{companion['emoji']} Echo returns the moment you spent. **+1 turn**.")

        if sum(1 for item in profile["equipment"].values() if item and item.get("set") == "last_banner") >= 3:
            stats_now = self._stats(profile)
            healed = min(stats_now["max_hp"] - profile["hp"], max(2, round(stats_now["max_hp"] * 0.04)))
            restored = min(stats_now["max_mana"] - profile["mana"], 3)
            profile["hp"] += healed
            profile["mana"] += restored
            if healed or restored:
                lines.append(f"📯 The Last Banner restores **{healed} health** and **{restored} mana**.")
        if "clarity" in equipped_effects:
            restored = min(self._stats(profile)["max_mana"] - profile["mana"], 2)
            profile["mana"] += restored
            if restored:
                lines.append(f"💠 Clarity restores **{restored} mana**.")
        if "absolution" in equipped_effects:
            for condition in list(profile["status"]):
                profile["status"][condition] = max(0, int(profile["status"][condition]) - 1)
                if profile["status"][condition] <= 0:
                    profile["status"].pop(condition, None)

        contract = profile.get("active_contract") or {}
        if contract:
            contract["progress"] = min(contract["target"], contract["progress"] + 1)
            if contract["progress"] >= contract["target"]:
                profile["gold"] += contract["gold"]
                profile["xp"] += contract["xp"]
                profile["contracts_completed"] += 1
                profile["reputation"] += 2
                lines.append(
                    f"📜 **Contract complete: {contract['title']}** — "
                    f"{self._money(profile, contract['gold'])}, {contract['xp']} XP, and 2 reputation.",
                )
                self._journal(profile, f"Completed the contract “{contract['title']}.”")
                profile["active_contract"] = {}
                lines.extend(self._apply_level_ups(profile))
        rift = profile.get("rift_state") or {}
        if rift:
            profile["rooms_cleared"] = max(0, profile["rooms_cleared"] - 1)
            rift["wave"] += 1
            if rift["wave"] < rift["waves"]:
                wave_seed = int(rift.get("seed", 0)) + rift["wave"]
                wave_rng = random.Random(wave_seed) if wave_seed else random
                next_enemy = enemy_for_floor(
                    rift["challenge_floor"] + rift["wave"],
                    wave_rng,
                )
                next_enemy = apply_affix(
                    next_enemy,
                    rift["challenge_floor"] + 10,
                    wave_rng,
                )
                next_enemy = self._apply_challenge_enemy_modifier(
                    next_enemy,
                    rift.get("name", ""),
                    wave_rng,
                )
                next_enemy["name"] = f"Riftbound {next_enemy['name']}"
                profile["combat_flags"].pop("web_used", None)
                profile["encounter"] = ensure_enemy_intent(next_enemy)
                lines.append(
                    f"🌀 **Rift Wave {rift['wave'] + 1}/{rift['waves']}** tears itself open.",
                )
            else:
                reward = round(
                    (180 + rift["challenge_floor"] * 14) * float(rift.get("reward_multiplier", 1.0)),
                )
                profile["gold"] += reward
                profile["season_points"] += 50 if rift["kind"] == "rift" else 30
                if rift["kind"] == "rift":
                    profile["rifts_completed"] += 1
                else:
                    profile["daily_date"] = rift["date"]
                    profile["daily_score"] = max(profile["daily_score"], rift["challenge_floor"])
                profile["floor"] = rift["original_floor"]
                profile["rooms_cleared"] = rift["original_rooms"]
                profile["rift_state"] = {}
                lines.append(
                    f"🌀 **Challenge complete!** {self._money(profile, reward)} and "
                    f"{'50' if rift['kind'] == 'rift' else '30'} season points awarded.",
                )
        return lines

    def _apply_level_ups(self, profile: dict[str, Any]) -> list[str]:
        lines = []
        while profile["xp"] >= xp_for_level(profile["level"]):
            required = xp_for_level(profile["level"])
            old_stats = self._stats(profile)
            profile["xp"] -= required
            profile["level"] += 1
            profile["attribute_points"] += 2
            if profile["level"] % 2 == 0:
                profile["talent_points"] += 1
            new_stats = self._stats(profile)
            profile["hp"] += new_stats["max_hp"] - old_stats["max_hp"]
            profile["mana"] = new_stats["max_mana"]
            lines.append(
                f"🌟 **LEVEL UP!** You are now level **{profile['level']}**. Your wounds mend and your power grows.",
            )
        return lines

    def _apply_death(self, profile: dict[str, Any], cause: str) -> str:
        equipped_effects = equipment_effects(profile.get("equipment", {}))
        if profile.get("talents", {}).get("second_wind", 0) and profile.get("free_revive", True):
            profile["free_revive"] = False
            profile["hp"] = 1
            return "🚩 **Second Wind** refuses death. You remain standing at **1 health**."
        if "rebirth" in equipped_effects and not profile.get("combat_flags", {}).get("legendary_rebirth"):
            profile["combat_flags"]["legendary_rebirth"] = True
            profile["hp"] = max(1, round(self._stats(profile)["max_hp"] * 0.3))
            if profile.get("encounter"):
                profile["encounter"]["status"]["burn"] = 5
            return "🔥 **Embermaw's Last Scale** resurrects you and ignites your enemy."
        if "margin" in equipped_effects and not profile.get("combat_flags", {}).get("margin_saved"):
            profile["combat_flags"]["margin_saved"] = True
            profile["hp"] = 1
            return "📖 **Armor Between Lines** writes your death into the margin. You remain at **1 health**."
        if (
            "oath_of_return" in profile.get("legacy", {}).get("active_tenets", [])
            and not profile.get("combat_flags", {}).get("tenet_death_save_used")
        ):
            profile["combat_flags"]["tenet_death_save_used"] = True
            profile["combat_flags"]["tenet_death_save_penalty"] = True
            profile["hp"] = 1
            return "◆ **Oath of Return** holds you at **1 health**. This encounter's rewards are reduced by 10%."
        enemy = dict(profile.get("encounter") or {})
        nemesis_line = ""
        if enemy.get("nemesis_id"):
            record_nemesis_escape(profile, int(enemy["nemesis_id"]))
            nemesis_line = f"\n👁️ **{enemy.get('name', 'Your Nemesis')}** survives and grows stronger."
        elif enemy:
            nemesis = create_nemesis(profile, enemy)
            if nemesis:
                nemesis_line = f"\n👁️ **Nemesis born:** {nemesis['name']} has learned how you fight."
        if profile.get("hardcore"):
            profile["deaths"] += 1
            profile["hardcore_dead"] = True
            profile["encounter"] = {}
            profile["choice"] = {}
            profile["active_puzzle"] = {}
            profile["rift_state"] = {}
            profile["combat_flags"] = {}
            profile["skill_cooldowns"] = {}
            profile["hp"] = 0
            return (
                f"☠️ **HARDCORE DEATH.** {profile['character_name']} falls to {cause}. "
                f"This chronicle is permanently sealed.{nemesis_line}"
            )
        loss = min(profile["gold"], max(10, round(profile["gold"] * 0.15)))
        profile["gold"] -= loss
        profile["deaths"] += 1
        profile["encounter"] = {}
        profile["choice"] = {}
        profile["active_puzzle"] = {}
        profile["status"] = {}
        profile["combat_flags"] = {}
        profile["skill_cooldowns"] = {}
        failed_challenge = restore_challenge_origin(profile)
        if not failed_challenge:
            profile["rooms_cleared"] = 0
            profile["floor"] = max(1, profile["floor"] - 1)
        stats = self._stats(profile)
        profile["hp"] = stats["max_hp"]
        profile["mana"] = stats["max_mana"]
        if profile.get("deepest_floor", 1) >= 5 and len(profile["scars"]) < 5 and random.random() < 0.25:
            scar = random.choice([entry for entry in SCARS if entry not in profile["scars"]] or list(SCARS))
            if scar not in profile["scars"]:
                profile["scars"].append(scar)
        retreat_text = "return to your interrupted expedition" if failed_challenge else f"retreat to floor **{profile['floor']}**"
        return (
            f"☠️ You fall to **{cause}**. Outpost scouts drag you back from the dark.\n"
            f"You lose **{self._money(profile, loss)}** and {retreat_text}.{nemesis_line}"
        )

    @staticmethod
    def _award_achievements(profile: dict[str, Any]) -> str:
        earned = set(profile["achievements"])
        eligible = {
            "first_blood": profile["kills"] >= 1,
            "delver_five": profile["deepest_floor"] >= 5,
            "boss_slayer": profile["bosses"] >= 1,
            "wealthy": profile["gold"] >= 1000,
            "veteran": profile["kills"] >= 100,
            "deep_twenty": profile["deepest_floor"] >= 20,
            "contractor": profile.get("contracts_completed", 0) >= 1,
            "lorekeeper": len(profile.get("lore", [])) >= 5,
            "master_smith": profile.get("crafted", 0) >= 10,
            "riddlemaster": len(profile.get("solved_puzzles", [])) >= 5,
            "bonded": any(int(data.get("bond", 0)) >= 50 for data in profile.get("companions", {}).values()),
            "professional": int(profile.get("profession", {}).get("level", 1)) >= 10,
            "chronicler": bool(profile.get("campaign", {}).get("ending")),
        }
        messages = []
        for key, condition in eligible.items():
            if not condition or key in earned:
                continue
            achievement = ACHIEVEMENTS[key]
            profile["achievements"].append(key)
            profile["gold"] += achievement["gold"]
            messages.append(
                f"🏅 **Achievement: {achievement['name']}** — {achievement['description']} "
                f"(+{DeepDelve._money(profile, achievement['gold'])})",
            )
        return "\n".join(messages)

    async def _town_interaction(self, interaction: discord.Interaction, action: str) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if not profile["created"]:
                await interaction.edit_original_response(embed=self._not_created_embed(), view=None)
                return
            if profile["encounter"]:
                await interaction.followup.send(
                    "You cannot use town services while an enemy is chasing you.",
                    ephemeral=True,
                )
                return

            stats = self._stats(profile)
            if action == "rest":
                cost = self._rest_price(profile)
                fully_rested = (
                    profile["hp"] >= stats["max_hp"]
                    and not profile.get("status")
                    and not profile.get("conviction_fatigue", 0)
                )
                if fully_rested:
                    narrative = "The innkeeper glances at you. “You look rested enough already.”"
                elif profile["gold"] < cost:
                    narrative = f"A bed costs **{self._money(profile, cost)}**, and the innkeeper does not offer credit."
                else:
                    profile["gold"] -= cost
                    profile["hp"] = stats["max_hp"]
                    profile["status"] = {}
                    profile["conviction_fatigue"] = 0
                    narrative = f"You sleep without dreams and awaken at full health. **-{self._money(profile, cost)}**"
            elif action == "potion":
                cost = self._potion_price(profile)
                if profile["gold"] < cost:
                    narrative = f"The apothecary asks **{self._money(profile, cost)}**. Your purse comes up short."
                elif profile["potions"] >= 10:
                    narrative = "Your potion satchel is full. Ten glass bottles are enough to worry about."
                else:
                    profile["gold"] -= cost
                    profile["potions"] += 1
                    narrative = f"You purchase a crimson healing potion. **-{self._money(profile, cost)}**"
            else:
                cost = max(5, profile["level"] * 3)
                if profile["mana"] >= stats["max_mana"]:
                    narrative = "Your mind is already clear and your mana is full."
                elif profile["gold"] < cost:
                    narrative = f"The chapel requests a **{self._money(profile, cost)}** offering."
                else:
                    profile["gold"] -= cost
                    profile["mana"] = stats["max_mana"]
                    narrative = f"The chapel's flame restores your mana. **-{self._money(profile, cost)}**"

            await self._save_profile(
                interaction.guild.id,
                interaction.user.id,
                profile,
                starting_gold,
            )
        await interaction.edit_original_response(
            embed=self._town_embed(profile, narrative),
            view=TownView(self, interaction.user.id),
        )

    async def _contract_interaction(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            contract = profile.get("active_contract") or {}
            if contract:
                narrative = (
                    f"📜 **{contract['title']}** remains active: "
                    f"**{contract['progress']}/{contract['target']}** enemies defeated. "
                    f"Reward: **{self._money(profile, contract['gold'])}** and **{contract['xp']} XP**."
                )
            else:
                region = region_for_floor(profile["floor"])
                target = min(10, 3 + profile["level"] // 3)
                reward_gold = 40 + profile["floor"] * 8 + target * 6
                mara_reputation = int(profile["npc_reputation"].get("mara", 0))
                reward_gold = round(
                    reward_gold * (1 + min(0.2, mara_reputation * 0.01)),
                )
                reward_xp = 35 + profile["floor"] * 9
                contract = {
                    "title": f"Thin the Shadows of {region['name']}",
                    "region": region["name"],
                    "target": target,
                    "progress": 0,
                    "gold": reward_gold,
                    "xp": reward_xp,
                }
                profile["active_contract"] = contract
                self._journal(profile, f"Accepted the contract “{contract['title']}.”")
                narrative = (
                    f"📜 **New Contract: {contract['title']}**\n"
                    f"Defeat **{target} enemies** anywhere in the Deep.\n"
                    f"Reward: **{self._money(profile, reward_gold)}**, **{reward_xp} XP**, "
                    "and **2 Lastlight reputation**."
                )
                await self._save_profile(guild_id, user_id, profile, starting_gold)
        await interaction.edit_original_response(
            embed=self._town_embed(profile, narrative),
            view=TownView(self, user_id),
        )

    async def _show_crafting_interaction(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self._get_profile(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(
            embed=self._craft_embed(profile),
            view=CraftView(self, interaction.user.id),
        )

    async def _craft_interaction(self, interaction: discord.Interaction, slot: str) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._lock_for(guild_id, user_id):
            profile = await self._get_profile(guild_id, user_id)
            starting_gold = profile["gold"]
            region = region_for_floor(profile["floor"])
            material_key = region["material"]
            material = MATERIALS[material_key]
            cost = self._craft_cost(profile)
            narrative: str
            if len(profile["inventory"]) >= 25:
                narrative = "Orra refuses to work while your pack is full."
            elif profile["materials"].get(material_key, 0) < 3:
                narrative = f"You need **3 {material['name']}** to forge at your current depth."
            elif profile["gold"] < cost:
                narrative = f"Orra requires **{self._money(profile, cost)}** for the work."
            else:
                profile["materials"][material_key] -= 3
                profile["gold"] -= cost
                stats = self._stats(profile)
                item = self._generate_item(
                    profile,
                    profile["floor"] + 2,
                    stats["luck"] + 4,
                    slot=slot,
                )
                forge_level = int(profile.get("town_bonus", {}).get("crafted_bonus", 0))
                profession_level = (
                    int(profile.get("profession", {}).get("level", 1))
                    if profile.get("profession", {}).get("key") == "blacksmith"
                    else 0
                )
                bonus_levels = min(3, forge_level // 2 + profession_level // 10)
                if bonus_levels:
                    item["upgrade"] = int(item.get("upgrade", 0)) + bonus_levels
                    for stat in ("attack", "defense", "hp", "luck"):
                        if item.get(stat):
                            item[stat] = max(1, round(item[stat] * (1 + bonus_levels * 0.08)))
                profile["inventory"].append(item)
                self._record_set_discovery(profile, item)
                profile["crafted"] += 1
                self._journal(profile, f"Orra forged {item['name']} from {material['name']}.")
                narrative = (
                    f"Flame bends toward Orra's hammer. You receive "
                    f"**{item['rarity']} {item['name']}** — {item_stat_line(item)}.\n"
                    f"**-3 {material['name']} • -{self._money(profile, cost)}**"
                )
                profession_lines = grant_profession_xp(profile, 25 + profile["floor"])
                if profession_lines:
                    narrative += "\n" + "\n".join(profession_lines)
                commission_lines = progress_commission(profile, "craft")
                if commission_lines:
                    narrative += "\n" + "\n".join(commission_lines)
                achievement_text = self._award_achievements(profile)
                if achievement_text:
                    narrative += f"\n\n{achievement_text}"
                await self._save_profile(guild_id, user_id, profile, starting_gold)
        await interaction.edit_original_response(
            embed=self._craft_embed(profile, narrative),
            view=CraftView(self, user_id),
        )

    async def _show_inventory_interaction(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        profile = await self._get_profile(interaction.guild.id, interaction.user.id)
        if not profile["created"]:
            await interaction.edit_original_response(embed=self._not_created_embed(), view=None)
            return
        await interaction.edit_original_response(
            embed=self._inventory_embed(profile),
            view=InventoryView(self, interaction.user.id, profile),
        )

    async def _profession_select_interaction(self, interaction: discord.Interaction, key: str) -> None:
        """Choose a profession from the persistent menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        if key not in PROFESSIONS:
            await interaction.followup.send("That profession is unavailable.", ephemeral=True)
            return
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            current_key = profile.get("profession", {}).get("key", "")
            if current_key == key:
                narrative = f"You are already a **{PROFESSIONS[key]['name']}**."
            else:
                cost = 0 if not current_key else 150 + int(profile["level"]) * 15
                if profile["gold"] < cost:
                    await interaction.followup.send(
                        f"Changing professions costs **{self._money(profile, cost)}**.",
                        ephemeral=True,
                    )
                    return
                current = profile.get("profession", {})
                if current.get("key"):
                    profile["profession_mastery"][current["key"]] = {
                        "level": int(current.get("level", 1)),
                        "xp": int(current.get("xp", 0)),
                    }
                restored = profile["profession_mastery"].get(key, {"level": 1, "xp": 0})
                profile["profession"] = {"key": key, **restored}
                profile["gold"] -= cost
                narrative = (
                    f"{PROFESSIONS[key]['emoji']} You are now a **{PROFESSIONS[key]['name']}**. "
                    f"{'Your first calling is free.' if not cost else f'Changing paths cost {self._money(profile, cost)}.'}"
                )
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        embed = self._profession_embed(profile)
        embed.description = f"{narrative}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=ProfessionView(self, interaction.user.id, profile),
        )

    async def _profession_gather_interaction(self, interaction: discord.Interaction) -> None:
        """Use a daily gathering action from the profession menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if not profile.get("profession", {}).get("key"):
                await interaction.followup.send("Choose a profession from this menu first.", ephemeral=True)
                return
            today = datetime.now(timezone.utc).date().isoformat()
            if profile.get("gather_date") != today:
                profile["gather_date"] = today
                profile["gather_actions"] = 0
            if int(profile.get("gather_actions", 0)) >= 3:
                await interaction.followup.send(
                    "All three gathering actions are used. They reset at 00:00 UTC.",
                    ephemeral=True,
                )
                return
            if int(profile.get("turns", 0)) < 1:
                await interaction.followup.send("Gathering costs 1 energy, but none remains.", ephemeral=True)
                return
            profile["turns"] -= 1
            result = gather(profile)
            profile["gather_actions"] += 1
            lines = [*progress_commission(profile, "gather"), *progress_quests(profile, "recover")]
            await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        narrative = (
            f"{result['emoji']} Gathered **{result['amount']} {result['name']}**. "
            f"**{3 - profile['gather_actions']}** daily actions and **{profile['turns']} energy** remain."
        )
        if result["potion"]:
            narrative += "\n⚗️ Your technique also produced one potion."
        if result["messages"] or lines:
            narrative += "\n" + "\n".join([*result["messages"], *lines])
        embed = self._profession_embed(profile)
        embed.description = f"{narrative}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=ProfessionView(self, interaction.user.id, profile),
        )

    async def _companion_select_interaction(self, interaction: discord.Interaction, key: str) -> None:
        """Activate a discovered companion from the roster menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if key == "none" or key not in profile.get("companions", {}) or key not in COMPANIONS:
                await interaction.followup.send("No discovered companion matches that choice.", ephemeral=True)
                return
            profile["active_companion"] = key
            await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        embed = self._companion_embed(profile)
        embed.description = (
            f"{COMPANIONS[key]['emoji']} **{COMPANIONS[key]['name']} joins your expedition.**\n\n"
            f"{embed.description}"
        )
        await interaction.edit_original_response(
            embed=embed,
            view=CompanionView(self, interaction.user.id, profile),
        )

    async def _commission_select_interaction(self, interaction: discord.Interaction, index: int) -> None:
        """Accept a weekly commission from its menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            ok, message = accept_commission(profile, index)
            if ok:
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        if not ok:
            await interaction.followup.send(message, ephemeral=True)
            return
        embed = self._commissions_embed(profile)
        embed.description = f"{message}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=CommissionsView(self, interaction.user.id, profile),
        )

    async def _quest_menu_interaction(
        self,
        interaction: discord.Interaction,
        action: str,
        key: str,
        outcome: str = "",
    ) -> None:
        """Accept or resolve a quest from the journal selector."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if action == "accept":
                ok, message = accept_quest(profile, key)
            elif action == "resolve":
                ok, message = resolve_quest(profile, key, outcome)
                if ok:
                    self._apply_level_ups(profile)
            else:
                ok, message = False, "Unknown quest action."
            if ok:
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        if not ok:
            await interaction.followup.send(message, ephemeral=True)
            return
        embed = self._quest_journal_embed(profile)
        embed.description = f"{message}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=QuestJournalView(self, interaction.user.id, profile),
        )

    async def _atlas_menu_interaction(
        self,
        interaction: discord.Interaction,
        action: str,
        value: str,
    ) -> None:
        """Advance and resolve named dungeons entirely through the Atlas menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if action == "enter":
                ok, message = enter_dungeon(profile, value)
            elif action == "choice":
                ok, message = resolve_dungeon_choice(profile, value)
            elif action == "advance":
                ok, message = advance_dungeon(profile)
                if ok:
                    progress = [
                        *progress_quests(profile, "explore"),
                        *progress_quests(profile, "delve"),
                        *progress_oath(profile, "explore"),
                        *progress_oath(profile, "delve"),
                    ]
                    if progress:
                        message += "\n" + "\n".join(progress)
            elif action == "abandon":
                ok, message = abandon_dungeon(profile)
            else:
                ok, message = False, "Unknown Atlas action."
            if ok:
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        if not ok:
            await interaction.followup.send(message, ephemeral=True)
            return
        embed = self._atlas_embed(profile)
        embed.description = f"{message}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=AtlasView(self, interaction.user.id, profile),
        )

    async def _saga_menu_interaction(self, interaction: discord.Interaction, choice: str) -> None:
        """Advance the Living Chronicle from its persistent controls."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            result = advance_living_campaign(profile, choice or None)
            if result["ok"]:
                if result.get("resolved"):
                    progress = [
                        *progress_quests(profile, "decision"),
                        *progress_oath(profile, "resolve"),
                    ]
                    if progress:
                        result["message"] += "\n" + "\n".join(progress)
                self._apply_level_ups(profile)
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        if not result["ok"]:
            await interaction.followup.send(result["message"], ephemeral=True)
            return
        await interaction.edit_original_response(
            embed=self._living_campaign_embed(profile, result["message"]),
            view=SagaView(self, interaction.user.id, profile),
        )

    async def _archive_menu_interaction(
        self,
        interaction: discord.Interaction,
        action: str,
        chapter: int,
    ) -> None:
        """Begin or advance a permanent seasonal chapter from its menu."""
        if not interaction.guild:
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            if action == "begin":
                ok, message = begin_season_chapter(profile, chapter)
            elif action == "advance":
                ok, message = advance_season_chapter(profile)
                if ok:
                    self._apply_level_ups(profile)
            else:
                ok, message = False, "Unknown archive action."
            if ok:
                await self._save_profile(interaction.guild.id, interaction.user.id, profile, starting_gold)
        if not ok:
            await interaction.followup.send(message, ephemeral=True)
            return
        embed = self._season_archive_embed(profile)
        embed.description = f"{message}\n\n{embed.description}"
        await interaction.edit_original_response(
            embed=embed,
            view=SeasonArchiveView(self, interaction.user.id, profile),
        )

    async def _inventory_interaction(
        self,
        interaction: discord.Interaction,
        selected_id: str | None,
        action: str,
    ) -> None:
        if not interaction.guild:
            return
        if not selected_id or selected_id == "empty":
            await interaction.response.send_message("Select an item first.", ephemeral=True)
            return
        await interaction.response.defer()
        async with self._lock_for(interaction.guild.id, interaction.user.id):
            profile = await self._get_profile(interaction.guild.id, interaction.user.id)
            starting_gold = profile["gold"]
            index = next(
                (index for index, item in enumerate(profile["inventory"]) if str(item["id"]) == selected_id),
                None,
            )
            if index is None:
                await interaction.followup.send(
                    "That item is no longer in your pack.",
                    ephemeral=True,
                )
                return
            item = profile["inventory"][index]
            favorite = str(item["id"]) in profile.get("favorite_items", [])
            if favorite and action in {"sell", "dismantle", "reroll"}:
                await interaction.followup.send(
                    "That item is favorited. Unfavorite it before altering or disposing of it.",
                    ephemeral=True,
                )
                return
            if action == "identify":
                if item.get("identified", True):
                    await interaction.followup.send("That item is already identified.", ephemeral=True)
                    return
                shard_cost = 3 + int(item.get("rarity_index", 0))
                if profile["arcane_shards"] < shard_cost:
                    await interaction.followup.send(
                        f"Identification requires **{shard_cost} arcane shards**.",
                        ephemeral=True,
                    )
                    return
                profile["arcane_shards"] -= shard_cost
                item["identified"] = True
                item["name"] = item.pop("hidden_name", item["name"])
                item["codex_key"] = item["name"].lower().replace(" ", "_")
                self._record_item(profile, item)
                narrative = f"🔮 Identified **{item['name']}** for **{shard_cost} arcane shards**."
            elif action == "equip":
                old_item = profile["equipment"].get(item["slot"])
                if not item.get("identified", True):
                    await interaction.followup.send(
                        "Identify that relic before equipping it.",
                        ephemeral=True,
                    )
                    return
                if old_item and old_item.get("cursed"):
                    await interaction.followup.send(
                        "Your equipped item is cursed and must be cleansed before replacement.",
                        ephemeral=True,
                    )
                    return
                profile["inventory"].pop(index)
                profile["equipment"][item["slot"]] = item
                if old_item:
                    profile["inventory"].append(old_item)
                stats = self._stats(profile)
                profile["hp"] = min(profile["hp"], stats["max_hp"])
                narrative = f"Equipped **{item['name']}** in your {item['slot']} slot."
            elif action == "sell":
                if item.get("bound"):
                    await interaction.followup.send(
                        "Bound equipment cannot be sold. It can still be dismantled.",
                        ephemeral=True,
                    )
                    return
                profile["inventory"].pop(index)
                sale_value = item_sale_value(item)
                profile["gold"] += sale_value
                narrative = f"Sold **{item['name']}** for **{self._money(profile, sale_value)}**."
            elif action == "dismantle":
                if item.get("origin"):
                    await interaction.followup.send(
                        "Origin weapons cannot be dismantled. They may be stored in your stash.",
                        ephemeral=True,
                    )
                    return
                profile["inventory"].pop(index)
                currency, shards = dismantle_rewards(item)
                profile["gold"] += currency
                profile["arcane_shards"] += shards
                narrative = (
                    f"Dismantled **{item['name']}** into **{shards} arcane shards** and **{self._money(profile, currency)}**."
                )
            elif action == "upgrade":
                upgrade_cap = int(item.get("upgrade_cap", 10))
                if int(item.get("upgrade", 0)) >= upgrade_cap:
                    await interaction.followup.send(
                        f"That item has reached its +{upgrade_cap} upgrade limit.",
                        ephemeral=True,
                    )
                    return
                currency, shards = upgrade_cost(item)
                if profile["gold"] < currency or profile["arcane_shards"] < shards:
                    await interaction.followup.send(
                        f"Upgrading requires {self._money(profile, currency)} and {shards} arcane shards.",
                        ephemeral=True,
                    )
                    return
                profile["gold"] -= currency
                profile["arcane_shards"] -= shards
                item["upgrade"] = int(item.get("upgrade", 0)) + 1
                for stat in ("attack", "defense", "hp", "luck"):
                    if item.get(stat):
                        item[stat] = max(item[stat] + 1, round(item[stat] * 1.12))
                narrative = f"Upgraded **{item['name']}** to **+{item['upgrade']}**."
            elif action == "enchant":
                shard_cost = 5 + int(item.get("rarity_index", 0)) * 2
                if profile["arcane_shards"] < shard_cost:
                    await interaction.followup.send(
                        f"Enchanting requires **{shard_cost} arcane shards**.",
                        ephemeral=True,
                    )
                    return
                enchantments = (
                    ("Ember Sigil", "burn", "Critical hits may Burn."),
                    ("Serpent Sigil", "poison", "Critical hits may Poison."),
                    ("Mender Sigil", "mending", "Victories restore additional health."),
                    ("Fortune Sigil", "fortune", "Victory currency is increased."),
                    ("Warden Sigil", "warding", "Elite damage is reduced."),
                )
                name, effect, description = random.choice(enchantments)
                profile["arcane_shards"] -= shard_cost
                item["enchant"] = name
                item["enchant_effect"] = effect
                item["enchant_description"] = description
                narrative = f"Inscribed **{name}** onto **{item['name']}**."
            else:
                if (
                    item.get("origin")
                    or item.get("legendary")
                    or item.get("boss_relic")
                    or item.get("set")
                    or item.get("bound")
                ):
                    await interaction.followup.send(
                        "Origin, legendary, set, boss, and bound relic identities cannot be rerolled.",
                        ephemeral=True,
                    )
                    return
                shard_cost = 3 + int(item.get("rarity_index", 0))
                currency_cost = max(25, int(item.get("value", 1)) // 2)
                if profile["arcane_shards"] < shard_cost or profile["gold"] < currency_cost:
                    await interaction.followup.send(
                        f"Rerolling requires {self._money(profile, currency_cost)} and {shard_cost} arcane shards.",
                        ephemeral=True,
                    )
                    return
                profile["arcane_shards"] -= shard_cost
                profile["gold"] -= currency_cost
                replacement = self._generate_item(
                    profile,
                    int(item.get("floor", profile["floor"])),
                    self._stats(profile)["luck"] + 2,
                    slot=item["slot"],
                )
                replacement["id"] = item["id"]
                profile["inventory"][index] = replacement
                self._record_set_discovery(profile, replacement)
                narrative = f"Rerolled **{item['name']}** into **{replacement['name']}**."
            await self._save_profile(
                interaction.guild.id,
                interaction.user.id,
                profile,
                starting_gold,
            )

        embed = self._inventory_embed(profile)
        embed.description = f"{narrative}\n\n" + (embed.description or "")
        await interaction.edit_original_response(
            embed=embed,
            view=InventoryView(self, interaction.user.id, profile),
        )

    async def _world_boss_strike(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        await interaction.response.defer()
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        async with self._guild_lock_for(guild_id):
            record = await self.config.guild(interaction.guild).world_boss()
            if not record:
                await interaction.followup.send("The world boss has already fallen.", ephemeral=True)
                return
            profile = await self._get_profile(guild_id, user_id)
            if not profile["created"] or profile.get("hardcore_dead"):
                await interaction.followup.send(
                    "You need a living DeepDelve character to join the raid.",
                    ephemeral=True,
                )
                return
            now = datetime.now(timezone.utc)
            last_text = record.get("last_attacks", {}).get(str(user_id))
            if last_text:
                elapsed = (now - datetime.fromisoformat(last_text)).total_seconds()
                if elapsed < 30:
                    await interaction.followup.send(
                        f"Recover for **{round(30 - elapsed)} more seconds**.",
                        ephemeral=True,
                    )
                    return
            stats = self._stats(profile)
            damage = random.randint(stats["attack"] * 2, stats["attack"] * 3 + stats["luck"])
            damage = round(
                damage * (1 + int(profile.get("guild_bonus", {}).get("worldboss_percent", 0)) / 100),
            )
            record["hp"] = max(0, int(record["hp"]) - damage)
            record.setdefault("contributions", {})[str(user_id)] = (
                int(record.get("contributions", {}).get(str(user_id), 0)) + damage
            )
            record.setdefault("last_attacks", {})[str(user_id)] = now.isoformat()
            defeated = record["hp"] <= 0
            if defeated:
                contributions = record["contributions"]
                total_damage = max(1, sum(int(value) for value in contributions.values()))
                reward_lines = []
                guild_renown: dict[str, int] = {}
                for member_id_text, contribution in contributions.items():
                    member_id = int(member_id_text)
                    member = interaction.guild.get_member(member_id)
                    if not member:
                        continue
                    member_profile = await self._get_profile(guild_id, member_id)
                    starting_gold = member_profile["gold"]
                    share = int(contribution) / total_damage
                    reward = 200 + round(record["max_hp"] * 0.12 * share)
                    member_profile["gold"] += reward
                    member_profile["xp"] += 150 + round(250 * share)
                    member_profile["season_points"] += 75
                    if member_profile.get("player_guild_id"):
                        guild_code = member_profile["player_guild_id"]
                        guild_renown[guild_code] = guild_renown.get(guild_code, 0) + max(
                            1,
                            round(int(contribution) / 10),
                        )
                    levels = self._apply_level_ups(member_profile)
                    await self._save_profile(
                        guild_id,
                        member_id,
                        member_profile,
                        starting_gold,
                    )
                    reward_lines.append(
                        f"<@{member_id}> — {self._money(member_profile, reward)}"
                        + (f" • {len(levels)} level-up(s)" if levels else ""),
                    )
                if guild_renown:
                    player_guilds = await self.config.guild(interaction.guild).player_guilds()
                    for guild_code, renown in guild_renown.items():
                        if guild_code in player_guilds:
                            player_guilds[guild_code]["renown"] += renown
                    await self.config.guild(interaction.guild).player_guilds.set(player_guilds)
                await self.config.guild(interaction.guild).world_boss.set({})
                await self.config.guild(interaction.guild).world_boss_defeated_at.set(
                    datetime.now(timezone.utc).isoformat(),
                )
                embed = discord.Embed(
                    title=f"🏆 WORLD BOSS DEFEATED — {record['name']}",
                    description=(f"<@{user_id}> delivers the final **{damage} damage**!\n\n" + "\n".join(reward_lines[:15])),
                    color=GOLD_COLOR,
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            await self.config.guild(interaction.guild).world_boss.set(record)
        embed = self._world_boss_embed(record)
        embed.description = f"<@{user_id}> deals **{damage} raid damage**!\n\n" + embed.description
        await interaction.edit_original_response(embed=embed, view=WorldBossView(self))

    @commands.hybrid_group(name="deepdelve", aliases=["delve"], invoke_without_command=True)
    @commands.guild_only()
    async def deepdelve(self, ctx: commands.Context) -> None:
        """Enter a persistent old-school dungeon-crawling adventure."""
        if not await self._channel_allowed(ctx):
            return
        profile = await self._get_profile(ctx.guild.id, ctx.author.id)
        if not profile["created"]:
            embed = discord.Embed(
                title="⚔️ DeepDelve",
                description=(
                    "Beneath Lastlight Outpost lies a dungeon without an end.\n\n"
                    "Choose a class, battle monsters, collect procedural equipment, "
                    "defeat bosses, and carve your name into the server leaderboard.\n\n"
                    "Begin with `/deepdelve create`."
                ),
                color=EMBED_COLOR,
            )
            art_path = Path(__file__).parent / "assets" / "deepdelve-key-art.png"
            if art_path.is_file():
                embed.set_image(url="attachment://deepdelve-key-art.png")
                await ctx.send(
                    embed=embed,
                    file=discord.File(art_path, filename="deepdelve-key-art.png"),
                )
            else:
                await ctx.send(embed=embed)
            return
        if not profile.get("origin_complete", True):
            await ctx.send(
                embed=self._origin_embed(profile),
                view=OriginView(self, ctx.author.id, profile),
            )
            return
        if profile.get("hardcore_dead"):
            await ctx.send(embed=self._hardcore_death_embed(profile))
            return
        await ctx.send(
            embed=self._game_hub_embed(profile),
            view=GameHubView(self, ctx.author.id),
        )

    @deepdelve.command(name="living")
    @commands.guild_only()
    async def living(
        self,
        ctx: commands.Context,
        section: str = "hub",
        action: str = "view",
        target: str = "",
        extra: str = "",
    ) -> None:
        """Use 5.0 systems: quests, atlas, tenets, oaths, saga, archive, bonds, commissions, and more."""
        section = section.lower()
        action = action.lower()
        if section in {"hub", "home"}:
            profile = await self._require_character(ctx)
            if profile:
                await ctx.send(embed=self._game_hub_embed(profile), view=GameHubView(self, ctx.author.id))
            return
        if section in {"quests", "quest"}:
            if action == "accept":
                await self.quests_accept(ctx, target)
            elif action == "resolve":
                await self.quests_resolve(ctx, target, extra)
            elif action in {"abandon", "fail"}:
                await self.quests_abandon(ctx, target)
            else:
                await self.quests_group(ctx)
        elif section == "atlas":
            if action == "enter":
                await self.atlas_enter(ctx, target)
            elif action == "advance":
                await self.atlas_advance(ctx)
            elif action == "abandon":
                await self.atlas_abandon(ctx)
            elif action == "choice":
                await self.atlas_choice(ctx, target)
            else:
                await self.atlas_group(ctx)
        elif section in {"tenets", "tenet"}:
            if action == "learn":
                await self.tenets_learn(ctx, target)
            elif action == "equip":
                await self.tenets_equip(ctx, keys=" ".join(value for value in (target, extra) if value))
            else:
                await self.tenets_group(ctx)
        elif section in {"oaths", "oath"}:
            if action == "accept":
                await self.oaths_accept(ctx, target)
            else:
                await self.oaths_group(ctx)
        elif section == "journey":
            await self.moral_journey(ctx, action if action != "view" else target)
        elif section == "echoes":
            await self.echoes(ctx)
        elif section == "mail":
            await self.mail(ctx, action)
        elif section == "sanctum":
            if action == "upgrade":
                await self.sanctum_upgrade(ctx, target)
            else:
                await self.sanctum_group(ctx)
        elif section == "service":
            await self.faction_service(ctx, action if action != "view" else target)
        elif section in {"relationships", "bonds"}:
            if action == "gift":
                await self.relationship_gift(ctx, target, extra)
            elif action == "favor":
                await self.relationship_favor(ctx, target)
            else:
                await self.relationships(ctx)
        elif section == "nemeses":
            await self.nemeses(ctx)
        elif section == "content":
            await self.living_content_status(ctx)
        elif section == "saga":
            await self.living_saga(ctx, action)
        elif section == "archive":
            if action == "begin":
                if not target.isdigit():
                    await ctx.send("Choose a numeric archive chapter.")
                else:
                    await self.season_archive_begin(ctx, int(target))
            elif action == "advance":
                await self.season_archive_advance(ctx)
            else:
                await self.season_archive_group(ctx)
        elif section in {"commissions", "commission"}:
            if action == "accept":
                if not target.isdigit():
                    await ctx.send("Choose commission 1, 2, or 3.")
                else:
                    await self.commissions_accept(ctx, int(target))
            elif action == "recipes":
                await self.commissions_recipes(ctx)
            elif action == "research":
                await self.commissions_research(ctx, target)
            else:
                await self.commissions_group(ctx)
        else:
            await ctx.send(
                "Choose `quests`, `atlas`, `tenets`, `oaths`, `journey`, `echoes`, `mail`, `sanctum`, "
                "`bonds`, `nemeses`, `saga`, `archive`, `commissions`, or `content`.",
            )

    async def quests_group(self, ctx: commands.Context) -> None:
        """Open the persistent quest journal."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(embed=self._quest_journal_embed(profile), view=QuestJournalView(self, ctx.author.id, profile))

    async def quests_accept(self, ctx: commands.Context, key: str) -> None:
        """Accept an available quest by its displayed key."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = accept_quest(profile, key.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def quests_resolve(self, ctx: commands.Context, key: str, outcome: str) -> None:
        """Resolve a ready quest through mercy, honesty, ambition, or ruthlessness."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = resolve_quest(profile, key.lower(), outcome.lower())
            if ok:
                self._apply_level_ups(profile)
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def quests_abandon(self, ctx: commands.Context, key: str) -> None:
        """Abandon an active quest and preserve its failure state."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = fail_quest(profile, key.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def atlas_group(self, ctx: commands.Context) -> None:
        """View named dungeons, routes, costs, and checkpoints."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(embed=self._atlas_embed(profile), view=AtlasView(self, ctx.author.id, profile))

    async def atlas_enter(self, ctx: commands.Context, key: str) -> None:
        """Enter a discovered named dungeon; entry itself is free."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = enter_dungeon(profile, key.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def atlas_advance(self, ctx: commands.Context) -> None:
        """Spend one displayed energy to advance the current named dungeon."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = advance_dungeon(profile)
            if ok:
                lines = [
                    *progress_quests(profile, "explore"),
                    *progress_quests(profile, "delve"),
                    *progress_oath(profile, "explore"),
                    *progress_oath(profile, "delve"),
                ]
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
                if lines:
                    message += "\n" + "\n".join(lines)
        await ctx.send(message)

    async def atlas_abandon(self, ctx: commands.Context) -> None:
        """Abandon to the last checkpoint without refunding spent energy."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = abandon_dungeon(profile)
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def atlas_choice(self, ctx: commands.Context, approach: str) -> None:
        """Resolve a named-dungeon moral event or puzzle approach."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = resolve_dungeon_choice(profile, approach)
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def tenets_group(self, ctx: commands.Context) -> None:
        """View Resolve and the 18 balanced moral-path sidegrades."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        legacy = ensure_legacy(profile)
        path = morality_path(profile)["key"]
        broad_path = "radiant" if path in {"radiant", "beacon"} else "umbral" if path in {"umbral", "dreadbound"} else "pragmatic"
        lines = []
        for key, tenet in TENETS.items():
            if tenet["path"] != broad_path:
                continue
            marker = "⭐" if key in legacy["active_tenets"] else "✅" if key in legacy["unlocked_tenets"] else "🔒"
            lines.append(f"{marker} **{tenet['name']}** · {tenet['kind'].title()}\n`{key}` — {tenet['description']}")
        embed = discord.Embed(
            title=f"◆ {broad_path.title()} Tenets — {legacy['resolve']} Resolve",
            description="\n\n".join(lines),
            color=morality_path(profile)["color"],
        )
        embed.set_footer(text="Learning costs 2 Resolve. Equip up to three; Tenets are tactical sidegrades.")
        await ctx.send(embed=embed)

    async def tenets_learn(self, ctx: commands.Context, key: str) -> None:
        """Learn a Tenet for two non-tradable Resolve."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = unlock_tenet(profile, key.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def tenets_equip(self, ctx: commands.Context, *, keys: str) -> None:
        """Equip up to three learned Tenet keys separated by spaces."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        selected = [key.lower() for key in keys.replace(",", " ").split() if key.lower() not in {"none", "clear"}]
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = equip_tenets(profile, selected)
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def oaths_group(self, ctx: commands.Context) -> None:
        """View today's equal-value ideological assignments."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            board = oath_board(profile)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        lines = [
            (
                f"{FACTIONS[entry['faction']]['emoji']} **{entry['name']}** — {FACTIONS[entry['faction']]['name']}\n"
                f"`{entry['faction']}` • {entry['objective']} {entry['target']} time(s) • "
                f"{entry['reward']['gold']} currency + {entry['reward']['xp']} XP + "
                f"{entry['reward']['faction_reputation']} reputation"
            )
            for entry in board
        ]
        embed = discord.Embed(
            title="📜 Daily Oath Board",
            description="\n\n".join(lines),
            color=0xAAB7B8,
        )
        embed.set_footer(text="Equal reward value • Use /deepdelve living oaths accept <faction>.")
        await ctx.send(embed=embed)

    async def oaths_accept(self, ctx: commands.Context, faction: str) -> None:
        """Accept today's oath for lantern, concord, or court."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = accept_oath(profile, faction.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def moral_journey(self, ctx: commands.Context, target: str) -> None:
        """Begin a slow three-stage journey toward radiant, pragmatic, or umbral."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = begin_redemption(profile, target.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def echoes(self, ctx: commands.Context) -> None:
        """See concrete consequences the world remembers."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(
                embed=discord.Embed(
                    title="🌌 World Echoes",
                    description="\n".join(world_echoes(profile)),
                    color=morality_path(profile)["color"],
                ),
            )

    async def mail(self, ctx: commands.Context, action: str = "view") -> None:
        """Read permanent letters and Lastlight notices."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            generate_mail(profile)
            if action.lower() == "read":
                profile["mail_read"] = list(
                    dict.fromkeys(
                        [
                            *profile.get("mail_read", []),
                            *(letter["key"] for letter in profile["mailbox"]),
                        ],
                    ),
                )
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(embed=self._mail_embed(profile), view=GameHubView(self, ctx.author.id))

    async def sanctum_group(self, ctx: commands.Context) -> None:
        """View the capped personal restoration and collection space."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(embed=self._sanctum_embed(profile), view=GameHubView(self, ctx.author.id))

    async def sanctum_upgrade(self, ctx: commands.Context, room: str) -> None:
        """Restore one Sanctum room using ordinary currency."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = upgrade_sanctum(profile, room.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def faction_service(self, ctx: commands.Context, faction: str) -> None:
        """Use one unlocked equal-budget faction contact per UTC day."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = use_faction_service(profile, faction.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def relationships(self, ctx: commands.Context) -> None:
        """View trust, conflict, favors, and remembered relationship states."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        entries = ensure_relationships(profile)
        lines = [
            (
                f"👤 **{key.title()} — {relationship_level(entry)}**\n"
                f"Trust {entry['trust']}/50 • Conflict {entry['conflict']}/50 • {len(entry['flags'])} memories"
            )
            for key, entry in entries.items()
        ]
        await ctx.send(embed=discord.Embed(title="👥 Bonds of Lastlight", description="\n\n".join(lines), color=0x3498DB))

    async def relationship_gift(self, ctx: commands.Context, character: str, material: str) -> None:
        """Give one daily material gift; every character has a preference."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = give_gift(profile, character.lower(), material.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def relationship_favor(self, ctx: commands.Context, character: str) -> None:
        """Request one weekly personal-hunt lead from a trusted character."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = request_favor(profile, character.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def nemeses(self, ctx: commands.Context) -> None:
        """View enemies that learned your name after defeating you."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        state = ensure_nemeses(profile)
        lines = [
            f"👁️ **{entry['name']}** · level {entry['level']}\n{entry['trait_text']} • last seen floor {entry['floor']}"
            for entry in state["active"]
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"👁️ Personal Nemeses — {len(state['active'])}/3",
                description="\n\n".join(lines) or "No enemy has survived long enough to learn your name.",
                color=DANGER_COLOR,
            ),
        )

    async def living_content_status(self, ctx: commands.Context) -> None:
        """Show the installed 5.0 content package and validation status."""
        counts = content_counts()
        errors = validate_content()
        await ctx.send(
            embed=discord.Embed(
                title="📦 DeepDelve 5.0 Content Registry",
                description="\n".join(f"**{key.replace('_', ' ').title()}:** {value}" for key, value in counts.items()),
                color=SUCCESS_COLOR if not errors else DANGER_COLOR,
            ).set_footer(text="Registry valid" if not errors else f"{len(errors)} validation error(s)"),
        )

    async def living_saga(self, ctx: commands.Context, action: str = "view") -> None:
        """Play the six-act Living Chronicle; decisions use conviction names."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if action.lower() == "view":
            await ctx.send(embed=self._living_campaign_embed(profile))
            return
        choice = action.lower() if action.lower() in {"mercy", "honesty", "ambition", "ruthlessness"} else None
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            result = advance_living_campaign(profile, choice)
            if result["ok"]:
                if result.get("resolved"):
                    result["message"] += "\n" + "\n".join(
                        [
                            *progress_quests(profile, "decision"),
                            *progress_oath(profile, "resolve"),
                        ],
                    )
                self._apply_level_ups(profile)
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(embed=self._living_campaign_embed(profile, result["message"]))

    async def season_archive_group(self, ctx: commands.Context) -> None:
        """View twelve permanent seasonal story chapters and catch-up access."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = []
        for chapter in season_chapter_status(profile):
            marker = "✅" if chapter["completed"] else "📖" if chapter["active"] else "📚" if chapter["available"] else "🔒"
            detail = "Archived permanently" if chapter["completed"] else "Active" if chapter["active"] else (
                "Available forever" if chapter["available"] else chapter["locked_reason"]
            )
            lines.append(f"{marker} **{chapter['index']}. {chapter['name']}** — {detail}")
        embed = discord.Embed(
            title=f"📚 Seasonal Archive — {len(profile.get('season_archive', []))}/12",
            description="\n".join(lines),
            color=0x5B2C6F,
        )
        embed.set_footer(text="Chapters never expire • Begin with /deepdelve living archive begin <number>.")
        await ctx.send(embed=embed)

    async def season_archive_begin(self, ctx: commands.Context, chapter: int) -> None:
        """Begin an available permanent seasonal chapter."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = begin_season_chapter(profile, chapter)
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def season_archive_advance(self, ctx: commands.Context) -> None:
        """Spend the displayed energy to advance an active archive chapter."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = advance_season_chapter(profile)
            if ok:
                self._apply_level_ups(profile)
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def commissions_group(self, ctx: commands.Context) -> None:
        """View three deterministic weekly profession commissions."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            offers = commission_board(profile)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        active = profile.get("commissions", {}).get("active", {})
        lines = [
            (
                f"⚒️ **{index}. {offer['name']}**\n"
                f"{offer['objective'].title()} {offer['target']} time(s) • "
                f"{offer['reward']['gold']} currency • {offer['reward']['xp']} XP • "
                f"{offer['reward']['mastery']} mastery"
            )
            for index, offer in enumerate(offers, start=1)
        ]
        if active:
            lines.insert(0, f"⭐ **Active: {active['name']}** — {active['progress']}/{active['target']}")
        await ctx.send(
            embed=discord.Embed(
                title="⚒️ Weekly Profession Commissions",
                description="\n\n".join(lines),
                color=0xA04000,
            ).set_footer(text="Use /deepdelve living commissions accept <number>. Offers change weekly at UTC."),
        )

    async def commissions_accept(self, ctx: commands.Context, number: int) -> None:
        """Accept one offered weekly profession commission."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = accept_commission(profile, number)
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    async def commissions_recipes(self, ctx: commands.Context) -> None:
        """View Living World recipe research and its guaranteed costs."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        mastery = int(profile.get("profession_mastery_points", 0))
        lines = []
        for key, recipe in list(LIVING_RECIPES.items())[:15]:
            marker = "✅" if key in profile.get("recipes", []) else "📖" if mastery >= recipe["mastery"] else "🔒"
            materials = ", ".join(f"{amount} {material}" for material, amount in recipe["materials"].items())
            lines.append(
                f"{marker} **{recipe['name']}** · mastery {recipe['mastery']}\n"
                f"`{key}` • {recipe['gold_cost']} currency + {materials}",
            )
        await ctx.send(
            embed=discord.Embed(
                title=f"📖 Recipe Research — {mastery} mastery",
                description="\n\n".join(lines),
                color=0x7D6608,
            ).set_footer(text="Showing the first 15 of 30 recipes. Research by displayed key."),
        )

    async def commissions_research(self, ctx: commands.Context, key: str) -> None:
        """Research a gated recipe with currency and materials."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            ok, message = research_recipe(profile, key.lower())
            if ok:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(message)

    @deepdelve.command(name="create")
    @commands.guild_only()
    async def create(
        self,
        ctx: commands.Context,
        class_name: str | None = None,
        *,
        character_name: str | None = None,
    ) -> None:
        """Create your delver, optionally providing a class and character name.

        Available classes: Vanguard, Shadow, and Arcanist.
        """
        if not await self._channel_allowed(ctx):
            return
        profile = await self._get_profile(ctx.guild.id, ctx.author.id)
        if profile["created"]:
            await ctx.send(
                "You already have a character. Use `/deepdelve retire` if you truly want to start over.",
            )
            return
        if class_name:
            class_key = class_name.lower().strip()
            aliases = {
                "warrior": "vanguard",
                "fighter": "vanguard",
                "rogue": "shadow",
                "thief": "shadow",
                "mage": "arcanist",
                "wizard": "arcanist",
            }
            class_key = aliases.get(class_key, class_key)
            if class_key not in GAME_CLASSES:
                await ctx.send(
                    f"Unknown class. Choose {humanize_list([details['name'] for details in GAME_CLASSES.values()])}.",
                )
                return
            name = (character_name or ctx.author.display_name).strip()[:32]
            if not name:
                name = ctx.author.display_name[:32]
            created = await self._create_character(ctx.guild.id, ctx.author.id, name, class_key)
            if not created:
                await ctx.send("Your character could not be created.")
                return
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            await ctx.send(
                embed=self._origin_embed(profile),
                view=OriginView(self, ctx.author.id, profile),
            )
            return

        embed = discord.Embed(
            title="⚔️ Choose Your Path",
            description=(
                "Your class determines your starting attributes and signature combat skill. "
                "Equipment and levels will let you shape the character from there."
            ),
            color=EMBED_COLOR,
        )
        for details in GAME_CLASSES.values():
            embed.add_field(
                name=f"{details['emoji']} {details['name']}",
                value=(
                    f"{details['description']}\n"
                    f"❤️ {details['max_hp']}  •  🔷 {details['max_mana']}  •  "
                    f"⚔️ {details['attack']}  •  🛡️ {details['defense']}  •  🍀 {details['luck']}\n"
                    f"**Skill:** {details['skill']}"
                ),
                inline=False,
            )
        await ctx.send(embed=embed, view=ClassSelectView(self, ctx.author.id))

    @deepdelve.command(name="adventure", aliases=["explore"])
    @commands.guild_only()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def adventure(self, ctx: commands.Context) -> None:
        """Explore the next room or resume an active battle."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["encounter"]:
            await ctx.send(
                embed=self._combat_embed(profile, "Your unfinished battle resumes."),
                view=CombatView(self, ctx.author.id, profile),
            )
            return
        if profile["choice"]:
            await ctx.send(
                embed=self._choice_embed(profile),
                view=ChoiceView(self, ctx.author.id, profile["choice"]),
            )
            return
        if profile.get("active_puzzle"):
            await ctx.send(
                embed=self._puzzle_embed(profile),
                view=PuzzleView(self, ctx.author.id, profile["active_puzzle"]),
            )
            return
        profile, narrative = await self._explore(ctx.guild.id, ctx.author.id)
        if profile["encounter"]:
            await ctx.send(
                embed=self._combat_embed(profile, narrative),
                view=CombatView(self, ctx.author.id, profile),
            )
        elif profile["choice"]:
            await ctx.send(
                embed=self._choice_embed(profile),
                view=ChoiceView(self, ctx.author.id, profile["choice"]),
            )
        elif profile.get("active_puzzle"):
            await ctx.send(
                embed=self._puzzle_embed(profile, narrative),
                view=PuzzleView(self, ctx.author.id, profile["active_puzzle"]),
            )
        else:
            await ctx.send(
                embed=self._adventure_embed(profile, narrative),
                view=AdventureView(self, ctx.author.id),
            )

    @deepdelve.command(name="profile", aliases=["character"])
    @commands.guild_only()
    async def profile(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """View your character or another member's character."""
        if not await self._channel_allowed(ctx):
            return
        member = member or ctx.author
        profile = await self._get_profile(ctx.guild.id, member.id)
        if not profile["created"]:
            await ctx.send(f"{member.display_name} has not created a DeepDelve character.")
            return
        await ctx.send(embed=self._profile_embed(member, profile))

    @deepdelve.group(name="progression", aliases=["path"], invoke_without_command=True)
    @commands.guild_only()
    async def progression(self, ctx: commands.Context) -> None:
        """Manage attributes, talents, subclass, background, alignment, and titles."""
        profile = await self._require_character(ctx)
        if profile:
            refresh_titles(profile)
            await ctx.send(embed=self._progression_embed(profile))

    @progression.command(name="spend")
    @commands.guild_only()
    async def progression_spend(
        self,
        ctx: commands.Context,
        attribute: str,
        amount: int = 1,
    ) -> None:
        """Spend attribute points on might, finesse, insight, vitality, or fortune."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        attribute = attribute.lower()
        if attribute not in profile["attributes"]:
            await ctx.send("Choose `might`, `finesse`, `insight`, `vitality`, or `fortune`.")
            return
        if amount < 1 or amount > profile["attribute_points"]:
            await ctx.send(f"Choose an amount from 1 to {profile['attribute_points']}.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            if amount > profile["attribute_points"]:
                await ctx.send("Your available points changed. Try again.")
                return
            profile["attribute_points"] -= amount
            profile["attributes"][attribute] += amount
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"Added **{amount} point(s)** to **{attribute.title()}**.")

    @progression.command(name="talent")
    @commands.guild_only()
    async def progression_talent(self, ctx: commands.Context, talent: str) -> None:
        """Invest one point in a class talent using its displayed key or name."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        talent_key = talent.lower().replace(" ", "_")
        definition = talent_definition(profile, talent_key)
        if not definition:
            names = [entry["key"] for entry in TALENT_TREES[profile["class_key"]]]
            await ctx.send(f"Choose one of: {humanize_list(names)}.")
            return
        if profile["talent_points"] < 1:
            await ctx.send("You have no unspent talent points.")
            return
        rank = int(profile["talents"].get(talent_key, 0))
        if rank >= definition["max"]:
            await ctx.send("That talent is already at its maximum rank.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["talent_points"] -= 1
            profile["talents"][talent_key] = rank + 1
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            f"◆ **{definition['name']}** is now rank **{rank + 1}/{definition['max']}**.",
        )

    @progression.command(name="subclass")
    @commands.guild_only()
    async def progression_subclass(self, ctx: commands.Context, subclass: str | None = None) -> None:
        """Choose a permanent subclass at level 10."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        options = subclass_options(profile)
        if profile["subclass"]:
            current = options[profile["subclass"]]
            await ctx.send(f"You are already a {current['emoji']} **{current['name']}**.")
            return
        if profile["level"] < 10:
            await ctx.send(f"Subclasses unlock at level 10. You are level {profile['level']}.")
            return
        if not subclass:
            lines = [
                f"{details['emoji']} **{key}** — {details['description']}\nPassive: {details['passive']}"
                for key, details in options.items()
            ]
            await ctx.send(
                embed=discord.Embed(
                    title="🌠 Choose Your Subclass",
                    description="\n\n".join(lines),
                    color=GOLD_COLOR,
                ),
            )
            return
        subclass = subclass.lower()
        if subclass not in options:
            await ctx.send(f"Choose: {humanize_list(list(options))}.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            if profile["subclass"]:
                await ctx.send("Your subclass was already chosen.")
                return
            profile["subclass"] = subclass
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        chosen = options[subclass]
        await ctx.send(
            f"{chosen['emoji']} **Your path becomes {chosen['name']}.**\n{chosen['description']}",
        )

    @progression.command(name="background")
    @commands.guild_only()
    async def progression_background(self, ctx: commands.Context, background: str | None = None) -> None:
        """Choose a background before defeating your first enemy."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["background"]:
            details = BACKGROUNDS[profile["background"]]
            await ctx.send(f"Your background is **{details['name']}**.")
            return
        if profile["kills"] or profile["deepest_floor"] > 1:
            await ctx.send("Your history is already being written; a background can no longer be chosen.")
            return
        if not background:
            lines = [f"{details['emoji']} **{key}** — {details['description']}" for key, details in BACKGROUNDS.items()]
            await ctx.send(
                embed=discord.Embed(
                    title="📖 Choose Your Background",
                    description="\n\n".join(lines),
                    color=EMBED_COLOR,
                ),
            )
            return
        background = background.lower()
        if background not in BACKGROUNDS:
            await ctx.send(f"Choose: {humanize_list(list(BACKGROUNDS))}.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            details = BACKGROUNDS[background]
            profile["background"] = background
            for attribute, amount in details["attributes"].items():
                profile["attributes"][attribute] += amount
            profile["gold"] += details["gold"]
            profile["potions"] += details["potions"]
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"{details['emoji']} Your history: **{details['name']}**.\n{details['description']}")

    @progression.command(name="alignment")
    @commands.guild_only()
    async def progression_alignment(self, ctx: commands.Context, alignment: str | None = None) -> None:
        """View the permanent origin philosophy behind your living Morality."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not alignment:
            await ctx.send(
                f"Your origin philosophy is **{profile.get('alignment', 'Unwritten')}**. "
                f"Your deeds have made you **{morality_path(profile)['name']}** "
                f"({int(profile.get('morality', 0)):+d} Morality).",
            )
            return
        options = {"radiant": "Radiant", "pragmatic": "Pragmatic", "umbral": "Umbral"}
        key = alignment.lower()
        if key not in options:
            await ctx.send("Choose `Radiant`, `Pragmatic`, or `Umbral`.")
            return
        if profile.get("alignment") != "Unwritten":
            await ctx.send(
                "Your origin philosophy is permanent. It no longer dictates your path—your recorded deeds do.",
            )
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["alignment"] = options[key]
            if not profile.get("moral_deeds"):
                profile["morality"] = origin_morality(options[key])
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"Your unwritten origin now begins from a **{options[key]}** philosophy.")

    @progression.command(name="title")
    @commands.guild_only()
    async def progression_title(self, ctx: commands.Context, title: str | None = None) -> None:
        """View or equip an unlocked character title."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        refresh_titles(profile)
        if not title:
            lines = [f"`{key}` — **{TITLES[key][0]}**: {TITLES[key][1]}" for key in profile["titles"]]
            await ctx.send("\n".join(lines))
            return
        key = title.lower().replace(" ", "_")
        if key not in profile["titles"]:
            await ctx.send("You have not unlocked that title.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["current_title"] = key
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"Equipped the title **{TITLES[key][0]}**.")

    @progression.command(name="respec")
    @commands.guild_only()
    async def progression_respec(self, ctx: commands.Context) -> None:
        """Reset attributes and talents for a scaling currency cost."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        cost = 250 + profile["level"] * 75
        if profile["gold"] < cost:
            await ctx.send(f"Respecialization costs **{self._money(profile, cost)}**.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["gold"] -= cost
            base_attributes = {"might": 0, "finesse": 0, "insight": 0, "vitality": 0, "fortune": 0}
            background = BACKGROUNDS.get(profile["background"])
            if background:
                base_attributes.update(background["attributes"])
            profile["attributes"] = base_attributes
            profile["attribute_points"] = 5 + max(0, profile["level"] - 1) * 2
            profile["talents"] = {}
            profile["talent_points"] = 1 + max(0, profile["level"] - 1) // 2
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"Your build has been reset for **{self._money(profile, cost)}**.")

    @deepdelve.command(name="inventory", aliases=["pack"])
    @commands.guild_only()
    async def inventory(self, ctx: commands.Context) -> None:
        """Open your equipment pack."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        await ctx.send(
            embed=self._inventory_embed(profile),
            view=InventoryView(self, ctx.author.id, profile),
        )

    @deepdelve.command(name="town")
    @commands.guild_only()
    async def town(self, ctx: commands.Context) -> None:
        """Visit Lastlight Outpost for healing and supplies."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["encounter"]:
            await ctx.send("You cannot return to town in the middle of a battle.")
            return
        await ctx.send(embed=self._town_embed(profile), view=TownView(self, ctx.author.id))

    @deepdelve.command(name="achievements")
    @commands.guild_only()
    async def achievements(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ) -> None:
        """View achievement progress."""
        if not await self._channel_allowed(ctx):
            return
        member = member or ctx.author
        profile = await self._get_profile(ctx.guild.id, member.id)
        if not profile["created"]:
            await ctx.send(f"{member.display_name} has not created a character.")
            return
        earned = set(profile["achievements"])
        lines = []
        for key, details in ACHIEVEMENTS.items():
            icon = "🏅" if key in earned else "🔒"
            lines.append(
                f"{icon} **{details['name']}** — {details['description']} (*{self._money(profile, details['gold'])}*)",
            )
        embed = discord.Embed(
            title=f"🏅 {member.display_name}'s Achievements",
            description="\n".join(lines),
            color=GOLD_COLOR,
        )
        embed.set_footer(text=f"{len(earned)}/{len(ACHIEVEMENTS)} unlocked")
        await ctx.send(embed=embed)

    @deepdelve.command(name="bestiary")
    @commands.guild_only()
    async def bestiary(self, ctx: commands.Context) -> None:
        """View creatures you have encountered."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        discovered = profile["discovered"]
        if not discovered:
            description = "No creatures recorded. Explore the dungeon to begin your bestiary."
        else:
            description = "\n".join(f"• {name}" for name in discovered)
        await ctx.send(
            embed=discord.Embed(
                title="📖 Dungeon Bestiary",
                description=description,
                color=EMBED_COLOR,
            ),
        )

    @deepdelve.command(name="lore")
    @commands.guild_only()
    async def lore(self, ctx: commands.Context) -> None:
        """Read lore fragments recovered from the Deep."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        fragments = [fragment for fragment in LORE_FRAGMENTS if fragment["title"] in profile["lore"]]
        if not fragments:
            description = "Your chronicle contains no recovered lore. Study strange runes and search hidden rooms."
        else:
            description = "\n\n".join(f"📜 **{fragment['title']}**\n*{fragment['text']}*" for fragment in fragments)
        embed = discord.Embed(
            title="📚 Whispers of the Deep",
            description=description,
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"{len(fragments)}/{len(LORE_FRAGMENTS)} fragments recovered")
        await ctx.send(embed=embed)

    @deepdelve.command(name="journal")
    @commands.guild_only()
    async def journal(self, ctx: commands.Context) -> None:
        """Read the latest entries in your personal expedition journal."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        entries = profile.get("journal", [])
        description = "\n".join(f"• {entry}" for entry in entries[-20:])
        if not description:
            description = "The pages are blank. The Deep will provide the ink."
        await ctx.send(
            embed=discord.Embed(
                title=f"📓 {profile['character_name']}'s Expedition Journal",
                description=description,
                color=0x7D6608,
            ),
        )

    @deepdelve.command(name="materials")
    @commands.guild_only()
    async def materials(self, ctx: commands.Context) -> None:
        """View rare materials recovered for crafting."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = [
            f"{details['emoji']} **{details['name']}:** {profile['materials'].get(key, 0)}" for key, details in MATERIALS.items()
        ]
        await ctx.send(
            embed=discord.Embed(
                title="🧰 Crafting Materials",
                description="\n".join(lines),
                color=0xA04000,
            ),
        )

    @deepdelve.command(name="contract")
    @commands.guild_only()
    async def contract(self, ctx: commands.Context) -> None:
        """Visit the contract board to accept or review a bounty."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["encounter"]:
            await ctx.send("The contract board is in town, and you are currently fighting for your life.")
            return
        await ctx.send(embed=self._town_embed(profile), view=TownView(self, ctx.author.id))

    @deepdelve.command(name="craft")
    @commands.guild_only()
    async def craft(self, ctx: commands.Context) -> None:
        """Forge depth-scaled equipment from recovered materials."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["encounter"]:
            await ctx.send("Orra's forge is back in town. Finish your battle first.")
            return
        await ctx.send(embed=self._craft_embed(profile), view=CraftView(self, ctx.author.id))

    @deepdelve.command(name="regions", aliases=["world"], with_app_command=False)
    @commands.guild_only()
    async def regions(self, ctx: commands.Context) -> None:
        """View the known regions of the Deep."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = []
        for region in (
            region_for_floor(1),
            region_for_floor(6),
            region_for_floor(11),
            region_for_floor(16),
            region_for_floor(21),
        ):
            known = profile["deepest_floor"] >= int(region["floors"].split("–")[0].rstrip("+"))
            if known:
                lines.append(
                    f"{region['emoji']} **{region['name']}** — Floors {region['floors']}\n*{region['description']}*",
                )
            else:
                lines.append(f"❔ **Unknown Region** — Floors {region['floors']}")
        await ctx.send(
            embed=discord.Embed(
                title="🗺️ Cartography of the Deep",
                description="\n\n".join(lines),
                color=EMBED_COLOR,
            ),
        )

    @deepdelve.group(name="item", invoke_without_command=True)
    @commands.guild_only()
    async def item_group(self, ctx: commands.Context) -> None:
        """Inspect the equipment codex and advanced item systems."""
        await ctx.send_help(ctx.command)

    @item_group.command(name="inspect")
    @commands.guild_only()
    async def item_inspect(self, ctx: commands.Context, item_id: str) -> None:
        """Inspect an inventory or equipped item by its displayed ID."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        items = [
            *profile["inventory"],
            *profile.get("stash", []),
            *(item for item in profile["equipment"].values() if item),
        ]
        item = next(
            (entry for entry in items if str(entry["id"]) == item_id or entry["name"].lower() == item_id.lower()),
            None,
        )
        if not item:
            await ctx.send("No carried or equipped item matches that ID.")
            return
        currency_cost, shard_cost = upgrade_cost(item)
        embed = discord.Embed(
            title="🔎 Equipment Inspection",
            description=item_detail(item),
            color=RARITIES[int(item.get("rarity_index", 0))]["color"],
        )
        embed.add_field(
            name="Value",
            value=f"{self._money(profile, item['value'])}",
        )
        embed.add_field(
            name="Next Upgrade",
            value=f"{self._money(profile, currency_cost)} + {shard_cost} shards",
        )
        await ctx.send(embed=embed)

    @item_group.command(name="codex")
    @commands.guild_only()
    async def item_codex(self, ctx: commands.Context) -> None:
        """View equipment discoveries and legendary collection progress."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        discovered = profile.get("item_codex", [])
        legendary_names = {
            item["name"]
            for item in list(profile["inventory"]) + [item for item in profile["equipment"].values() if item]
            if item.get("legendary")
        }
        description = (
            f"📚 **Unique equipment discovered:** {len(discovered)}\n"
            f"🟠 **Legendary relics currently owned:** {len(legendary_names)}\n"
            f"🔷 **Arcane shards:** {profile.get('arcane_shards', 0)}\n\n"
            + (
                "\n".join(f"• {name}" for name in sorted(legendary_names))
                if legendary_names
                else "*No legendary relic has answered your call yet.*"
            )
        )
        await ctx.send(
            embed=discord.Embed(
                title="📕 The Relic Codex",
                description=description,
                color=GOLD_COLOR,
            ),
        )

    @item_group.command(name="sets")
    @commands.guild_only()
    async def item_sets(self, ctx: commands.Context) -> None:
        """View active bonuses and permanent set-discovery progress."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        _bonuses, effects = equipment_set_bonuses(profile["equipment"])
        progress = []
        for set_key, slots in profile.get("set_discoveries", {}).items():
            details = ITEM_SETS.get(set_key)
            if not details:
                continue
            found = set(slots)
            slot_marks = " ".join(
                f"{'✅' if slot in found else '⬛'} {slot.title()}"
                for slot in ("weapon", "armor", "charm")
            )
            fragments = int(profile.get("set_fragments", {}).get(set_key, 0))
            progress.append(f"**{details['name']}** — {slot_marks} • 🧩 {fragments}")
        sections = [
            "**Active Bonuses**\n" + ("\n".join(effects) if effects else "*None active.*"),
            "**Permanent Discoveries**\n" + ("\n".join(progress) if progress else "*No set pieces discovered.*"),
        ]
        description = "\n\n".join(sections)
        await ctx.send(
            embed=discord.Embed(
                title="🧩 Equipment Sets",
                description=description,
                color=EMBED_COLOR,
            ),
        )

    @item_group.command(name="completeset")
    @commands.guild_only()
    async def item_complete_set(self, ctx: commands.Context, set_key: str) -> None:
        """Forge a missing set slot after discovering two pieces and one duplicate."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        requested = set_key.lower().replace(" ", "_")
        set_key = next(
            (
                key
                for key, definition in ITEM_SETS.items()
                if requested in {key, definition["name"].lower().replace(" ", "_")}
            ),
            requested,
        )
        details = ITEM_SETS.get(set_key)
        discovered = set(profile.get("set_discoveries", {}).get(set_key, []))
        missing = [slot for slot in ("weapon", "armor", "charm") if slot not in discovered]
        if not details or len(discovered) < 2 or len(missing) != 1:
            await ctx.send("Discover two different slots from that set before attempting its final piece.")
            return
        if int(profile.get("set_fragments", {}).get(set_key, 0)) < 1:
            await ctx.send("Completing a set requires **1 fragment** converted from a duplicate piece.")
            return
        gold_cost = self._craft_cost(profile) * 2
        if profile["arcane_shards"] < 10 or profile["gold"] < gold_cost:
            await ctx.send(
                f"The final piece requires **10 shards** and **{self._money(profile, gold_cost)}**.",
            )
            return
        if len(profile["inventory"]) >= 25:
            await ctx.send("Your pack is full.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            discovered = set(profile.get("set_discoveries", {}).get(set_key, []))
            missing = [slot for slot in ("weapon", "armor", "charm") if slot not in discovered]
            if (
                len(missing) != 1
                or int(profile.get("set_fragments", {}).get(set_key, 0)) < 1
                or profile["arcane_shards"] < 10
                or profile["gold"] < gold_cost
                or len(profile["inventory"]) >= 25
            ):
                await ctx.send("Your set-forging requirements changed; review the collection and try again.")
                return
            item = generate_item(
                profile["floor"] + 2,
                self._stats(profile)["luck"] + 8,
                slot=missing[0],
                rarity_index=3,
            )
            item.update(
                {
                    "name": f"{details['name']} {item['name'].split()[-1]}",
                    "upgrade": 0,
                    "enchant": "",
                    "enchant_effect": "",
                    "enchant_description": "",
                    "identified": True,
                    "bound": False,
                    "set": set_key,
                    "unique_effect": "",
                    "effect_description": "",
                    "codex_key": f"set:{set_key}:{missing[0]}",
                },
            )
            profile["set_fragments"][set_key] -= 1
            profile["arcane_shards"] -= 10
            profile["gold"] -= gold_cost
            self._record_set_discovery(profile, item)
            profile["inventory"].append(item)
            self._record_item(profile, item)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            f"🧩 Orra completes **{details['name']}** with a new {missing[0]} piece — {item_stat_line(item)}.",
        )

    @item_group.command(name="identify")
    @commands.guild_only()
    async def item_identify(self, ctx: commands.Context, item_id: str) -> None:
        """Reveal an unidentified relic for arcane shards."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        item = next(
            (entry for entry in profile["inventory"] if str(entry["id"]) == item_id),
            None,
        )
        if not item or item.get("identified", True):
            await ctx.send("No unidentified inventory item matches that ID.")
            return
        cost = 3 + int(item.get("rarity_index", 0))
        if profile["arcane_shards"] < cost:
            await ctx.send(f"Identification requires **{cost} arcane shards**.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            item = next(entry for entry in profile["inventory"] if str(entry["id"]) == item_id)
            profile["arcane_shards"] -= cost
            item["identified"] = True
            item["name"] = item.pop("hidden_name", item["name"])
            item["codex_key"] = item["name"].lower().replace(" ", "_")
            self._record_item(profile, item)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"🔮 The relic is revealed:\n{item_detail(item)}")

    @item_group.command(name="cleanse")
    @commands.guild_only()
    async def item_cleanse(self, ctx: commands.Context, item_id: str) -> None:
        """Remove a curse from carried or equipped gear."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        items = profile["inventory"] + [item for item in profile["equipment"].values() if item]
        item = next((entry for entry in items if str(entry["id"]) == item_id), None)
        if not item or not item.get("cursed"):
            await ctx.send("No cursed carried or equipped item matches that ID.")
            return
        cost = 10 + int(item.get("rarity_index", 0)) * 4
        if profile["arcane_shards"] < cost:
            await ctx.send(f"Cleansing requires **{cost} arcane shards**.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            items = profile["inventory"] + [equipped for equipped in profile["equipment"].values() if equipped]
            item = next(entry for entry in items if str(entry["id"]) == item_id)
            profile["arcane_shards"] -= cost
            item["cursed"] = False
            if not item.get("legendary"):
                item["bound"] = False
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"✨ **{item['name']}** has been cleansed.")

    @item_group.command(name="favorite")
    @commands.guild_only()
    async def item_favorite(self, ctx: commands.Context, item_id: str) -> None:
        """Toggle protection for an item by ID."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            items = [
                *profile["inventory"],
                *profile.get("stash", []),
                *(item for item in profile["equipment"].values() if item),
            ]
            item = next((entry for entry in items if str(entry["id"]) == item_id), None)
            if not item:
                await ctx.send("No owned item matches that ID.")
                return
            favorites = profile.setdefault("favorite_items", [])
            if item_id in favorites:
                favorites.remove(item_id)
                state = "unfavorited"
            else:
                favorites.append(item_id)
                state = "favorited and protected"
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"⭐ **{item['name']}** is now {state}.")

    @item_group.command(name="stash")
    @commands.guild_only()
    async def item_stash(
        self,
        ctx: commands.Context,
        action: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """View the stash, or deposit/withdraw an item by ID."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not action:
            lines = [
                f"`{item['id']}` {'⭐ ' if str(item['id']) in profile.get('favorite_items', []) else ''}"
                f"**{item['name']}** — {item_stat_line(item)}"
                for item in profile.get("stash", [])
            ]
            shown = lines[:20]
            if len(lines) > 20:
                shown.append(f"\n*…and {len(lines) - 20} more. Withdraw by item ID.*")
            await ctx.send(
                embed=discord.Embed(
                    title=f"📦 Lastlight Vault — {len(lines)}/60",
                    description="\n".join(shown) or "*The vault is empty.*",
                    color=EMBED_COLOR,
                ),
            )
            return
        action = action.lower()
        if action not in {"deposit", "withdraw"} or not item_id:
            await ctx.send("Use `/deepdelve item stash deposit <id>` or `withdraw <id>`.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            source = profile["inventory"] if action == "deposit" else profile["stash"]
            target = profile["stash"] if action == "deposit" else profile["inventory"]
            limit = 60 if action == "deposit" else 25
            item = next((entry for entry in source if str(entry["id"]) == item_id), None)
            if not item:
                await ctx.send(f"No item with that ID is available to {action}.")
                return
            if len(target) >= limit:
                await ctx.send("That destination is full.")
                return
            source.remove(item)
            target.append(item)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"📦 **{item['name']}** moved to your {'vault' if action == 'deposit' else 'pack'}.")

    @item_group.command(name="loadout")
    @commands.guild_only()
    async def item_loadout(
        self,
        ctx: commands.Context,
        action: str | None = None,
        *,
        name: str | None = None,
    ) -> None:
        """Save, equip, delete, or list equipment loadouts."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not action or action.lower() == "list":
            owned = {
                str(item["id"]): item["name"]
                for item in [
                    *profile["inventory"],
                    *profile.get("stash", []),
                    *(item for item in profile["equipment"].values() if item),
                ]
            }
            lines = [
                f"• **{loadout_name}** — "
                + ", ".join(
                    f"{slot.title()}: {owned.get(item_id, 'missing') if item_id else 'empty'}"
                    for slot, item_id in slots.items()
                )
                for loadout_name, slots in profile.get("loadouts", {}).items()
            ]
            await ctx.send("🧰 **Loadouts**\n" + ("\n".join(lines) if lines else "*None saved.*"))
            return
        action = action.lower()
        loadout_name = (name or "").strip().lower()[:24]
        if action not in {"save", "equip", "delete"} or not loadout_name:
            await ctx.send("Use `/deepdelve item loadout save|equip|delete <name>`.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            loadouts = profile.setdefault("loadouts", {})
            if action == "save":
                if loadout_name not in loadouts and len(loadouts) >= 3:
                    await ctx.send("You may save up to three loadouts.")
                    return
                loadouts[loadout_name] = {slot: str(item["id"]) if item else "" for slot, item in profile["equipment"].items()}
                narrative = f"Saved **{loadout_name}**."
            elif action == "delete":
                if loadout_name not in loadouts:
                    await ctx.send("No loadout has that name.")
                    return
                del loadouts[loadout_name]
                narrative = f"Deleted **{loadout_name}**."
            else:
                if profile.get("encounter"):
                    await ctx.send("You cannot change loadouts during combat.")
                    return
                selected = loadouts.get(loadout_name)
                if not selected:
                    await ctx.send("No loadout has that name.")
                    return
                all_items = [
                    *profile["inventory"],
                    *profile.get("stash", []),
                    *(item for item in profile["equipment"].values() if item),
                ]
                by_id = {str(item["id"]): item for item in all_items}
                wanted = {slot: by_id.get(item_id) if item_id else None for slot, item_id in selected.items()}
                if any(item_id and wanted.get(slot) is None for slot, item_id in selected.items()):
                    await ctx.send("One or more loadout items are no longer owned.")
                    return
                if any(item and item.get("cursed") for item in profile["equipment"].values()):
                    await ctx.send("A cursed equipped item prevents changing loadouts.")
                    return
                wanted_ids = {str(item["id"]) for item in wanted.values() if item}
                remaining = [item for item in all_items if str(item["id"]) not in wanted_ids]
                if len(remaining) > 85:
                    await ctx.send("Your pack and vault cannot hold the displaced equipment.")
                    return
                profile["equipment"] = {slot: wanted.get(slot) for slot in ("weapon", "armor", "charm")}
                profile["inventory"] = remaining[:25]
                profile["stash"] = remaining[25:]
                stats = self._stats(profile)
                profile["hp"] = min(profile["hp"], stats["max_hp"])
                narrative = f"Equipped **{loadout_name}**."
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(f"🧰 {narrative}")

    @item_group.command(name="autodismantle")
    @commands.guild_only()
    async def item_auto_dismantle(self, ctx: commands.Context, rarity: str = "off") -> None:
        """Automatically dismantle ordinary drops at or below a rarity."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        rarity = rarity.lower()
        lookup = {entry["name"].lower(): index for index, entry in enumerate(RARITIES)}
        if rarity not in {*lookup, "off"}:
            await ctx.send("Choose `off`, `common`, `uncommon`, `rare`, `epic`, or `legendary`.")
            return
        threshold = -1 if rarity == "off" else lookup[rarity]
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["auto_dismantle"] = threshold
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            "🔨 Auto-dismantle disabled."
            if threshold < 0
            else f"🔨 Ordinary **{RARITIES[threshold]['name']} and lower** drops will be dismantled.",
        )

    @item_group.command(name="consumables", aliases=["supplies"])
    @commands.guild_only()
    async def item_consumables(self, ctx: commands.Context) -> None:
        """List carried tactical consumables."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = [
            f"{CONSUMABLES[key]['emoji']} `{key}` **{CONSUMABLES[key]['name']} ×{amount}** — {CONSUMABLES[key]['description']}"
            for key, amount in profile.get("consumables", {}).items()
            if amount > 0 and key in CONSUMABLES
        ]
        await ctx.send(
            embed=discord.Embed(
                title="🧪 Expedition Supplies",
                description="\n".join(lines) or "*No tactical supplies carried.*",
                color=EMBED_COLOR,
            ),
        )

    @item_group.command(name="use")
    @commands.guild_only()
    async def item_use(self, ctx: commands.Context, key: str) -> None:
        """Use a restorative consumable outside combat."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile.get("encounter"):
            await ctx.send("Use the **Tactical Item** selector on the active battle embed.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["_calculated_stats"] = self._stats(profile)
            result = use_consumable(profile, key.lower())
            profile.pop("_calculated_stats", None)
            if result["ok"]:
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(result["message"])

    @item_group.command(name="recipes")
    @commands.guild_only()
    async def item_recipes(self, ctx: commands.Context) -> None:
        """View forge patterns unlocked through rumors."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = [
            f"📜 `{key}` **{RECIPES[key]['name']}** — {RECIPES[key]['slot'].title()}"
            for key in profile.get("recipes", [])
            if key in RECIPES
        ]
        await ctx.send("⚒️ **Known Patterns**\n" + ("\n".join(lines) if lines else "*Resolve rumors to learn patterns.*"))

    @item_group.command(name="forgepattern", aliases=["forge-recipe"])
    @commands.guild_only()
    async def item_forge_pattern(self, ctx: commands.Context, key: str) -> None:
        """Forge a guaranteed-effect item from an unlocked pattern."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        key = key.lower()
        if key not in profile.get("recipes", []) or key not in RECIPES:
            await ctx.send("You have not learned that pattern.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            recipe = RECIPES[key]
            region = region_for_floor(int(recipe["region"]) * 5 + 1)
            material_key = region["material"]
            material = MATERIALS[material_key]
            gold_cost = round(self._craft_cost(profile) * 1.5)
            if len(profile["inventory"]) >= 25:
                narrative = "Your pack is full."
            elif profile["materials"].get(material_key, 0) < 5:
                narrative = f"You need **5 {material['name']}**."
            elif profile["arcane_shards"] < 5 or profile["gold"] < gold_cost:
                narrative = f"The pattern requires **5 shards** and **{self._money(profile, gold_cost)}**."
            else:
                profile["materials"][material_key] -= 5
                profile["arcane_shards"] -= 5
                profile["gold"] -= gold_cost
                craft_floor = profile["floor"] + 3
                rarity_index = 3 if profile["floor"] >= 15 else 2
                item = generate_item(
                    craft_floor,
                    self._stats(profile)["luck"] + 10,
                    slot=recipe["slot"],
                    rarity_index=rarity_index,
                )
                item.update(
                    {
                        "name": f"{recipe['name'].removesuffix(' Pattern')} {item['name'].split(maxsplit=1)[-1]}",
                        "upgrade": 0,
                        "enchant": "",
                        "enchant_effect": "",
                        "enchant_description": "",
                        "identified": True,
                        "bound": False,
                        "set": "",
                        "legendary": False,
                        "cursed": False,
                        "pattern": key,
                        "unique_effect": recipe["effect"],
                        "effect_description": f"Pattern effect: {recipe['name']}.",
                        "source": recipe["name"],
                    },
                )
                item["codex_key"] = item["name"].lower().replace(" ", "_")
                profile["inventory"].append(item)
                profile["crafted"] += 1
                self._record_item(profile, item)
                narrative = f"⚒️ Forged **{item['name']}** — {item_stat_line(item)}."
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(narrative)

    @item_group.command(name="collection")
    @commands.guild_only()
    async def item_collection(self, ctx: commands.Context) -> None:
        """View permanent discovery and relic collection progress."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        owned = [
            *profile["inventory"],
            *profile.get("stash", []),
            *(item for item in profile["equipment"].values() if item),
        ]
        legendary = {item["name"] for item in owned if item.get("legendary")}
        legendary_discovered = set(profile.get("legendary_codex", [])) | legendary
        sets = {item["set"] for item in owned if item.get("set")}
        sets_discovered = set(profile.get("set_discoveries", {})) | sets
        await ctx.send(
            embed=discord.Embed(
                title="🏛️ The Delver's Collection",
                description=(
                    f"📕 **Equipment discoveries:** {len(profile.get('item_codex', []))}\n"
                    f"🟠 **Legendary relics:** {len(legendary_discovered)} discovered • {len(legendary)} owned\n"
                    f"🧩 **Sets:** {len(sets_discovered)} discovered • {len(sets)} currently represented\n"
                    f"🧱 **Set fragments:** {sum(profile.get('set_fragments', {}).values())}\n"
                    f"📜 **Patterns learned:** {len(profile.get('recipes', []))}/{len(RECIPES)}\n"
                    f"🏺 **Story relics:** {len(profile.get('story_relics', []))}/{len(STORY_RELICS)}\n"
                    f"📖 **Bestiary entries:** {len(profile.get('bestiary', {}))}"
                ),
                color=GOLD_COLOR,
            ),
        )

    @deepdelve.group(name="npc", invoke_without_command=True)
    @commands.guild_only()
    async def npc_group(self, ctx: commands.Context) -> None:
        """Meet Lastlight's recurring characters and advance their stories."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        lines = []
        for key in NPCS:
            progress = npc_progress(profile, key)
            npc = progress["npc"]
            lines.append(
                f"{npc['emoji']} **{key} — {npc['name']}**, {npc['role']}\n"
                f"{progress['relationship']} • Reputation {progress['reputation']}",
            )
        await ctx.send(
            embed=discord.Embed(
                title="🏘️ People of Lastlight",
                description="\n\n".join(lines),
                color=SUCCESS_COLOR,
            ),
        )

    @npc_group.command(name="talk")
    @commands.guild_only()
    async def npc_talk(self, ctx: commands.Context, npc: str) -> None:
        """Speak with Orra, Mara, Vesper, or Rook."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        npc = npc.lower()
        if npc not in NPCS:
            await ctx.send(f"Choose: {humanize_list(list(NPCS))}.")
            return
        progress = npc_progress(profile, npc)
        living_relationship = ensure_relationships(profile)[npc]
        details = progress["npc"]
        dialogue = details.get("dialogue", ())
        dialogue_index = min(
            len(dialogue) - 1,
            int(progress["reputation"]) // 5 + len(profile.get("campaign", {}).get("completed", [])),
        )
        spoken = dialogue[dialogue_index] if dialogue else details["introduction"]
        moral_reaction = npc_moral_reaction(profile, npc)
        quest_lines = []
        for quest in progress["quests"]:
            marker = "✅" if quest["completed"] else "⭐" if quest["eligible"] else "🔒"
            quest_lines.append(
                f"{marker} **{quest['name']}** — {quest['description']}",
            )
        embed = discord.Embed(
            title=f"{details['emoji']} {details['name']} — {details['role']}",
            description=(
                f"*{details['introduction']}*\n\n{spoken}"
                + (f"\n\n**They study what you have become.**\n{moral_reaction}" if moral_reaction else "")
            ),
            color=morality_path(profile)["color"],
        )
        embed.add_field(
            name=f"Relationship: {relationship_level(living_relationship)}",
            value=(
                f"Legacy reputation: **{progress['reputation']}** • "
                f"Trust: **{living_relationship['trust']}** • Conflict: **{living_relationship['conflict']}**"
            ),
            inline=False,
        )
        embed.add_field(name="Story Quests", value="\n".join(quest_lines), inline=False)
        await ctx.send(embed=embed)

    @npc_group.command(name="quest")
    @commands.guild_only()
    async def npc_quest(self, ctx: commands.Context, npc: str) -> None:
        """Claim the next completed story quest for an NPC."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        npc = npc.lower()
        if npc not in NPCS:
            await ctx.send(f"Choose: {humanize_list(list(NPCS))}.")
            return
        progress = npc_progress(profile, npc)
        quest = next(
            (entry for entry in progress["quests"] if entry["eligible"] and not entry["completed"]),
            None,
        )
        if not quest:
            await ctx.send("You have no completed, unclaimed story quest for that character.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            reward_gold = 100 + profile["level"] * 20
            reward_xp = 75 + profile["level"] * 15
            profile["story_flags"].append(quest["flag"])
            profile["npc_reputation"][npc] += 5
            change_relationship(profile, npc, trust=5, flag=f"legacy_quest:{quest['flag']}")
            profile["gold"] += reward_gold
            profile["xp"] += reward_xp
            if quest["flag"].endswith(":3"):
                available = [blessing["name"] for blessing in BLESSINGS if blessing["name"] not in profile["blessings"]]
                if available:
                    profile["blessings"].append(random.choice(available))
            level_lines = self._apply_level_ups(profile)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        text = (
            f"⭐ **Story Quest Complete: {quest['name']}**\n"
            f"{self._money(profile, reward_gold)} • {reward_xp} XP • 5 relationship reputation"
        )
        if level_lines:
            text += "\n" + "\n".join(level_lines)
        await ctx.send(text)

    @deepdelve.group(name="party", invoke_without_command=True)
    @commands.guild_only()
    async def party_group(self, ctx: commands.Context) -> None:
        """Create a cooperative party with up to four delvers."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not profile["party_id"]:
            await ctx.send("You are not in a party. Use `/deepdelve party create` or `join`.")
            return
        parties = await self.config.guild(ctx.guild).parties()
        party = parties.get(profile["party_id"])
        if not party:
            await ctx.send("Your former party no longer exists.")
            return
        mentions = [f"<@{member_id}>" for member_id in party["members"]]
        await ctx.send(
            embed=discord.Embed(
                title=f"🧭 Party {profile['party_id']}",
                description=(
                    f"**Leader:** <@{party['leader']}>\n"
                    f"**Members:** {humanize_list(mentions)}\n\n"
                    "Party members receive cooperative HP, Attack, and Luck bonuses."
                ),
                color=SUCCESS_COLOR,
            ),
        )

    @party_group.command(name="create")
    @commands.guild_only()
    async def party_create(self, ctx: commands.Context) -> None:
        """Create a new cooperative party."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["party_id"]:
            await ctx.send("Leave your current party first.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            parties = await self.config.guild(ctx.guild).parties()
            code = short_code("P", parties)
            parties[code] = {"leader": ctx.author.id, "members": [ctx.author.id]}
            await self.config.guild(ctx.guild).parties.set(parties)
            profile["party_id"] = code
            profile["party_bonus"] = party_bonus(1)
            await self.config.member(ctx.author).set(profile)
        await ctx.send(f"🧭 Created party **{code}**. Others can join with `/deepdelve party join {code}`.")

    @party_group.command(name="join")
    @commands.guild_only()
    async def party_join(self, ctx: commands.Context, code: str) -> None:
        """Join an existing party by code."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["party_id"]:
            await ctx.send("Leave your current party first.")
            return
        code = code.upper()
        async with self._guild_lock_for(ctx.guild.id):
            parties = await self.config.guild(ctx.guild).parties()
            party = parties.get(code)
            if not party:
                await ctx.send("No party uses that code.")
                return
            if len(party["members"]) >= 4:
                await ctx.send("That party already has four members.")
                return
            party["members"].append(ctx.author.id)
            parties[code] = party
            await self.config.guild(ctx.guild).parties.set(parties)
            profile["party_id"] = code
            await self.config.member(ctx.author).set(profile)
            await self._sync_party_bonuses(ctx.guild.id, party["members"])
        await ctx.send(f"🧭 Joined party **{code}** with {len(party['members'])} members.")

    @party_group.command(name="leave")
    @commands.guild_only()
    async def party_leave(self, ctx: commands.Context) -> None:
        """Leave your current party."""
        profile = await self._require_character(ctx)
        if not profile or not profile["party_id"]:
            await ctx.send("You are not in a party.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            parties = await self.config.guild(ctx.guild).parties()
            code = profile["party_id"]
            party = parties.get(code)
            if party:
                party["members"] = [member_id for member_id in party["members"] if member_id != ctx.author.id]
                if not party["members"]:
                    parties.pop(code, None)
                else:
                    if party["leader"] == ctx.author.id:
                        party["leader"] = party["members"][0]
                    parties[code] = party
                    await self._sync_party_bonuses(ctx.guild.id, party["members"])
                await self.config.guild(ctx.guild).parties.set(parties)
            profile["party_id"] = ""
            profile["party_bonus"] = {}
            profile["party_role"] = ""
            await self.config.member(ctx.author).set(profile)
        await ctx.send("You leave the party and continue alone.")

    @party_group.command(name="role")
    @commands.guild_only()
    async def party_role(self, ctx: commands.Context, role: str) -> None:
        """Choose Guardian, Striker, Support, or Scout cooperative specialization."""
        profile = await self._require_character(ctx)
        if not profile or not profile["party_id"]:
            await ctx.send("Join a party before selecting a cooperative role.")
            return
        roles = {
            "guardian": "+3 DEF",
            "striker": "+3 ATK",
            "support": "+10 HP",
            "scout": "+4 LUCK",
        }
        role = role.lower()
        if role not in roles:
            await ctx.send(f"Choose: {humanize_list(list(roles))}.")
            return
        profile["party_role"] = role
        await self.config.member(ctx.author).set(profile)
        await ctx.send(f"🧭 Party role set to **{role.title()}** ({roles[role]}).")

    @deepdelve.group(name="auction", invoke_without_command=True)
    @commands.guild_only()
    async def auction_group(self, ctx: commands.Context) -> None:
        """Trade equipment through the server auction house."""
        await self.auction_browse(ctx)

    @auction_group.command(name="browse")
    @commands.guild_only()
    async def auction_browse(self, ctx: commands.Context) -> None:
        """Browse current equipment listings."""
        if not await self._channel_allowed(ctx):
            return
        auctions = await self.config.guild(ctx.guild).auctions()
        if not auctions:
            await ctx.send("The auction board is empty.")
            return
        currency = (
            await bank.get_currency_name(ctx.guild) if await self.config.guild(ctx.guild).economy_mode() == "bank" else "gold"
        )
        lines = []
        for auction_id, record in list(auctions.items())[:20]:
            item = record["item"]
            lines.append(
                f"`{auction_id}` {RARITIES[item.get('rarity_index', 0)]['emoji']} "
                f"**{item['name']}** — {record['price']} {currency} • Seller <@{record['seller']}>",
            )
        await ctx.send(
            embed=discord.Embed(
                title="🏛️ Lastlight Auction House",
                description="\n".join(lines),
                color=GOLD_COLOR,
            ),
        )

    @auction_group.command(name="list")
    @commands.guild_only()
    async def auction_list(self, ctx: commands.Context, item_id: str, price: int) -> None:
        """List an inventory item for a fixed price."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if price < 1:
            await ctx.send("The listing price must be positive.")
            return
        index = next(
            (index for index, item in enumerate(profile["inventory"]) if str(item["id"]) == item_id),
            None,
        )
        if index is None:
            await ctx.send("No inventory item matches that ID.")
            return
        if profile["inventory"][index].get("bound"):
            await ctx.send("Bound equipment cannot be traded.")
            return
        if item_id in profile.get("favorite_items", []):
            await ctx.send("That item is favorited. Unfavorite it before listing it.")
            return
        fee = max(1, min(250, round(price * 0.02)))
        if profile["gold"] < fee:
            await ctx.send(f"Listing requires a non-refundable **{self._money(profile, fee)}** auction fee.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            auctions = await self.config.guild(ctx.guild).auctions()
            if len(auctions) >= 100:
                await ctx.send("The auction house has reached its 100-listing limit.")
                return
            auction_id = short_code("A", auctions)
            starting_gold = profile["gold"]
            profile["gold"] -= fee
            item = profile["inventory"].pop(index)
            auctions[auction_id] = {
                "seller": ctx.author.id,
                "item": item,
                "price": price,
                "created": datetime.now(timezone.utc).isoformat(),
            }
            await self.config.guild(ctx.guild).auctions.set(auctions)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            f"Listed **{item['name']}** as `{auction_id}` for **{self._money(profile, price)}**. "
            f"**{self._money(profile, fee)}** listing fee paid.",
        )

    @auction_group.command(name="buy")
    @commands.guild_only()
    async def auction_buy(self, ctx: commands.Context, auction_id: str) -> None:
        """Purchase an auction listing."""
        buyer = await self._require_character(ctx)
        if not buyer:
            return
        auction_id = auction_id.upper()
        async with self._guild_lock_for(ctx.guild.id):
            auctions = await self.config.guild(ctx.guild).auctions()
            record = auctions.get(auction_id)
            if not record:
                await ctx.send("That auction no longer exists.")
                return
            if record["seller"] == ctx.author.id:
                await ctx.send("You cannot buy your own listing.")
                return
            seller_member = ctx.guild.get_member(int(record["seller"]))
            if not seller_member:
                await ctx.send("The seller is no longer available in this server.")
                return
            buyer = await self._get_profile(ctx.guild.id, ctx.author.id)
            seller = await self._get_profile(ctx.guild.id, seller_member.id)
            if len(buyer["inventory"]) >= 25:
                await ctx.send("Your inventory is full.")
                return
            if buyer["gold"] < record["price"]:
                await ctx.send(f"You need **{self._money(buyer, record['price'])}**.")
                return
            buyer_start = buyer["gold"]
            seller_start = seller["gold"]
            buyer["gold"] -= record["price"]
            seller["gold"] += record["price"]
            buyer["inventory"].append(record["item"])
            self._record_item(buyer, record["item"])
            auctions.pop(auction_id)
            await self.config.guild(ctx.guild).auctions.set(auctions)
            await self._save_profile(ctx.guild.id, ctx.author.id, buyer, buyer_start)
            await self._save_profile(ctx.guild.id, seller_member.id, seller, seller_start)
        await ctx.send(
            f"Purchased **{record['item']['name']}** for **{self._money(buyer, record['price'])}**.",
        )

    @auction_group.command(name="cancel")
    @commands.guild_only()
    async def auction_cancel(self, ctx: commands.Context, auction_id: str) -> None:
        """Cancel your listing and recover its item."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        auction_id = auction_id.upper()
        async with self._guild_lock_for(ctx.guild.id):
            auctions = await self.config.guild(ctx.guild).auctions()
            record = auctions.get(auction_id)
            if not record or record["seller"] != ctx.author.id:
                await ctx.send("That is not one of your active listings.")
                return
            if len(profile["inventory"]) >= 25:
                await ctx.send("Make room in your inventory before cancelling.")
                return
            profile["inventory"].append(record["item"])
            auctions.pop(auction_id)
            await self.config.guild(ctx.guild).auctions.set(auctions)
            await self.config.member(ctx.author).set(profile)
        await ctx.send(f"Cancelled `{auction_id}` and recovered **{record['item']['name']}**.")

    @deepdelve.group(name="guild", invoke_without_command=True)
    @commands.guild_only()
    async def player_guild_group(self, ctx: commands.Context) -> None:
        """Create and grow a persistent player guild."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        guilds = await self.config.guild(ctx.guild).player_guilds()
        record = guilds.get(profile["player_guild_id"])
        if not record:
            await ctx.send("You are guildless. Use `/deepdelve guild create` or `join`.")
            return
        members = humanize_list([f"<@{member_id}>" for member_id in record["members"]])
        embed = discord.Embed(
            title=f"🏰 {record['name']} • Level {record['level']}",
            description=(
                f"**Code:** `{profile['player_guild_id']}`\n"
                f"**Guildmaster:** <@{record['owner']}>\n"
                f"**Members:** {members}\n"
                f"**Treasury:** {record['treasury']}\n"
                f"**Renown:** {record['renown']}/{record['level'] * 1000}"
            ),
            color=GOLD_COLOR,
        )
        embed.add_field(name="Perks", value="\n".join(f"• {perk}" for perk in guild_perks(record)))
        await ctx.send(embed=embed)

    @player_guild_group.command(name="create")
    @commands.guild_only()
    async def player_guild_create(self, ctx: commands.Context, *, name: str) -> None:
        """Found a player guild for 1,000 currency."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["player_guild_id"]:
            await ctx.send("Leave your current guild first.")
            return
        if not 3 <= len(name.strip()) <= 32:
            await ctx.send("Guild names must contain 3–32 characters.")
            return
        cost = 1000
        if profile["gold"] < cost:
            await ctx.send(f"Founding a guild costs **{self._money(profile, cost)}**.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            if any(record["name"].casefold() == name.strip().casefold() for record in guilds.values()):
                await ctx.send("A player guild already uses that name.")
                return
            code = short_code("G", guilds)
            starting_gold = profile["gold"]
            profile["gold"] -= cost
            profile["player_guild_id"] = code
            guilds[code] = {
                "name": name.strip(),
                "owner": ctx.author.id,
                "members": [ctx.author.id],
                "treasury": 0,
                "renown": 0,
                "level": 1,
                "vault": [],
            }
            await self.config.guild(ctx.guild).player_guilds.set(guilds)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
            await self._sync_player_guild_bonuses(ctx.guild.id, [ctx.author.id], 1)
        await ctx.send(f"🏰 Founded **{name.strip()}** with recruitment code `{code}`.")

    @player_guild_group.command(name="join")
    @commands.guild_only()
    async def player_guild_join(self, ctx: commands.Context, code: str) -> None:
        """Join a player guild using its recruitment code."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["player_guild_id"]:
            await ctx.send("Leave your current guild first.")
            return
        code = code.upper()
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            record = guilds.get(code)
            if not record:
                await ctx.send("No player guild uses that code.")
                return
            if len(record["members"]) >= 50:
                await ctx.send("That guild has reached its 50-member limit.")
                return
            record["members"].append(ctx.author.id)
            guilds[code] = record
            profile["player_guild_id"] = code
            await self.config.guild(ctx.guild).player_guilds.set(guilds)
            await self.config.member(ctx.author).set(profile)
            await self._sync_player_guild_bonuses(
                ctx.guild.id,
                record["members"],
                record["level"],
            )
        await ctx.send(f"🏰 Joined **{record['name']}**.")

    @player_guild_group.command(name="contribute")
    @commands.guild_only()
    async def player_guild_contribute(self, ctx: commands.Context, amount: int) -> None:
        """Contribute currency to guild renown and upgrades."""
        profile = await self._require_character(ctx)
        if not profile or not profile["player_guild_id"]:
            await ctx.send("You are not in a player guild.")
            return
        if amount < 1 or profile["gold"] < amount:
            await ctx.send("Choose a positive amount you can afford.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            record = guilds.get(profile["player_guild_id"])
            if not record:
                await ctx.send("Your guild record no longer exists.")
                return
            starting_gold = profile["gold"]
            profile["gold"] -= amount
            record["treasury"] += amount
            record["renown"] += amount
            levels = []
            while record["level"] < 5 and record["renown"] >= record["level"] * 1000:
                record["renown"] -= record["level"] * 1000
                record["level"] += 1
                levels.append(record["level"])
            guilds[profile["player_guild_id"]] = record
            await self.config.guild(ctx.guild).player_guilds.set(guilds)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
            await self._sync_player_guild_bonuses(
                ctx.guild.id,
                record["members"],
                record["level"],
            )
        message = f"Contributed **{self._money(profile, amount)}** to **{record['name']}**."
        if levels:
            message += f"\n🌟 The guild reached level **{levels[-1]}**!"
        await ctx.send(message)

    @player_guild_group.command(name="leave")
    @commands.guild_only()
    async def player_guild_leave(self, ctx: commands.Context) -> None:
        """Leave your player guild; ownership transfers automatically."""
        profile = await self._require_character(ctx)
        if not profile or not profile["player_guild_id"]:
            await ctx.send("You are not in a player guild.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            code = profile["player_guild_id"]
            record = guilds.get(code)
            if record:
                record["members"] = [member_id for member_id in record["members"] if member_id != ctx.author.id]
                if not record["members"]:
                    guilds.pop(code, None)
                else:
                    if record["owner"] == ctx.author.id:
                        record["owner"] = record["members"][0]
                    guilds[code] = record
                await self.config.guild(ctx.guild).player_guilds.set(guilds)
            profile["player_guild_id"] = ""
            profile["guild_bonus"] = {}
            await self.config.member(ctx.author).set(profile)
        await ctx.send("You leave your player guild.")

    @player_guild_group.command(name="leaderboard")
    @commands.guild_only()
    async def player_guild_leaderboard(self, ctx: commands.Context) -> None:
        """Rank player guilds by level, renown, and treasury."""
        if not await self._channel_allowed(ctx):
            return
        guilds = await self.config.guild(ctx.guild).player_guilds()
        rankings = sorted(
            guilds.items(),
            key=lambda entry: (
                int(entry[1]["level"]),
                int(entry[1]["renown"]),
                int(entry[1]["treasury"]),
            ),
            reverse=True,
        )[:10]
        lines = [
            f"`#{index}` **{record['name']}** — Level {record['level']} • "
            f"{record['renown']} renown • {len(record['members'])} members"
            for index, (_code, record) in enumerate(rankings, start=1)
        ]
        await ctx.send(
            embed=discord.Embed(
                title="🏰 Player Guild Rankings",
                description="\n".join(lines) or "No player guilds have been founded.",
                color=GOLD_COLOR,
            ),
        )

    @player_guild_group.command(name="vault")
    @commands.guild_only()
    async def player_guild_vault(self, ctx: commands.Context) -> None:
        """View equipment stored in the shared guild vault."""
        profile = await self._require_character(ctx)
        if not profile or not profile["player_guild_id"]:
            await ctx.send("You are not in a player guild.")
            return
        guilds = await self.config.guild(ctx.guild).player_guilds()
        record = guilds.get(profile["player_guild_id"], {})
        vault = record.get("vault", [])
        lines = [f"`{item['id']}` {RARITIES[item.get('rarity_index', 0)]['emoji']} **{item['name']}**" for item in vault]
        await ctx.send(
            embed=discord.Embed(
                title=f"🔐 {record.get('name', 'Guild')} Vault",
                description="\n".join(lines) or "The shared vault is empty.",
                color=EMBED_COLOR,
            ),
        )

    @player_guild_group.command(name="deposit")
    @commands.guild_only()
    async def player_guild_deposit(self, ctx: commands.Context, item_id: str) -> None:
        """Deposit a tradable inventory item into the guild vault."""
        profile = await self._require_character(ctx)
        if not profile or not profile["player_guild_id"]:
            await ctx.send("You are not in a player guild.")
            return
        index = next(
            (index for index, item in enumerate(profile["inventory"]) if str(item["id"]) == item_id),
            None,
        )
        if index is None or profile["inventory"][index].get("bound"):
            await ctx.send("No tradable inventory item matches that ID.")
            return
        if item_id in profile.get("favorite_items", []):
            await ctx.send("That item is favorited. Unfavorite it before depositing it.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            record = guilds.get(profile["player_guild_id"])
            if not record:
                await ctx.send("Your guild record no longer exists.")
                return
            vault = record.setdefault("vault", [])
            if len(vault) >= 30:
                await ctx.send("The guild vault is full.")
                return
            item = profile["inventory"].pop(index)
            vault.append(item)
            guilds[profile["player_guild_id"]] = record
            await self.config.guild(ctx.guild).player_guilds.set(guilds)
            await self.config.member(ctx.author).set(profile)
        await ctx.send(f"🔐 Deposited **{item['name']}** into the guild vault.")

    @player_guild_group.command(name="withdraw")
    @commands.guild_only()
    async def player_guild_withdraw(self, ctx: commands.Context, item_id: str) -> None:
        """Withdraw an item; only the guildmaster controls the shared vault."""
        profile = await self._require_character(ctx)
        if not profile or not profile["player_guild_id"]:
            await ctx.send("You are not in a player guild.")
            return
        if len(profile["inventory"]) >= 25:
            await ctx.send("Your inventory is full.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            guilds = await self.config.guild(ctx.guild).player_guilds()
            record = guilds.get(profile["player_guild_id"])
            if not record or record["owner"] != ctx.author.id:
                await ctx.send("Only the guildmaster can withdraw shared equipment.")
                return
            vault = record.setdefault("vault", [])
            index = next(
                (index for index, item in enumerate(vault) if str(item["id"]) == item_id),
                None,
            )
            if index is None:
                await ctx.send("No vault item matches that ID.")
                return
            item = vault.pop(index)
            profile["inventory"].append(item)
            guilds[profile["player_guild_id"]] = record
            await self.config.guild(ctx.guild).player_guilds.set(guilds)
            await self.config.member(ctx.author).set(profile)
        await ctx.send(f"🔓 Withdrew **{item['name']}** from the guild vault.")

    @deepdelve.group(name="arena", invoke_without_command=True)
    @commands.guild_only()
    async def arena_group(self, ctx: commands.Context) -> None:
        """Challenge other delvers to consensual arena matches."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(
                f"⚔️ Arena record: **{profile['arena_wins']} wins** and **{profile['arena_losses']} losses**.",
            )

    @arena_group.command(name="challenge")
    @commands.guild_only()
    async def arena_challenge(
        self,
        ctx: commands.Context,
        opponent: discord.Member,
        wager: int = 0,
    ) -> None:
        """Challenge a delver; optional wagers are escrowed and require acceptance."""
        challenger = await self._require_character(ctx)
        if not challenger:
            return
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.send("Choose another human member.")
            return
        defender = await self._get_profile(ctx.guild.id, opponent.id)
        if not defender["created"]:
            await ctx.send("That member has no DeepDelve character.")
            return
        if wager < 0 or challenger["gold"] < wager:
            await ctx.send("Choose a wager you can currently afford.")
            return
        async with self._guild_lock_for(ctx.guild.id):
            arenas = await self.config.guild(ctx.guild).arenas()
            duel_id = short_code("D", arenas)
            starting_gold = challenger["gold"]
            challenger["gold"] -= wager
            arenas[duel_id] = {
                "challenger": ctx.author.id,
                "opponent": opponent.id,
                "wager": wager,
                "status": "pending",
            }
            await self.config.guild(ctx.guild).arenas.set(arenas)
            await self._save_profile(ctx.guild.id, ctx.author.id, challenger, starting_gold)
        await ctx.send(
            f"⚔️ {opponent.mention}, **{ctx.author.display_name}** challenges you as `{duel_id}` "
            f"for **{self._money(challenger, wager)}**.\n"
            f"Accept with `/deepdelve arena accept {duel_id}`.",
        )

    @arena_group.command(name="accept")
    @commands.guild_only()
    async def arena_accept(self, ctx: commands.Context, duel_id: str) -> None:
        """Accept and resolve a pending arena challenge."""
        duel_id = duel_id.upper()
        async with self._guild_lock_for(ctx.guild.id):
            arenas = await self.config.guild(ctx.guild).arenas()
            duel = arenas.get(duel_id)
            if not duel or duel["status"] != "pending" or duel["opponent"] != ctx.author.id:
                await ctx.send("That is not a pending challenge addressed to you.")
                return
            challenger_member = ctx.guild.get_member(int(duel["challenger"]))
            if not challenger_member:
                await ctx.send("The challenger is no longer available.")
                return
            challenger = await self._get_profile(ctx.guild.id, challenger_member.id)
            defender = await self._get_profile(ctx.guild.id, ctx.author.id)
            if defender["gold"] < duel["wager"]:
                await ctx.send("You cannot currently cover the wager.")
                return
            defender_start = defender["gold"]
            challenger_start = challenger["gold"]
            defender["gold"] -= duel["wager"]
            challenger_power = arena_power(challenger, self._stats(challenger))
            defender_power = arena_power(defender, self._stats(defender))
            total = max(2, challenger_power + defender_power)
            challenger_wins = random.randint(1, total) <= challenger_power
            winner = challenger if challenger_wins else defender
            loser = defender if challenger_wins else challenger
            winner_member = challenger_member if challenger_wins else ctx.author
            loser_member = ctx.author if challenger_wins else challenger_member
            winner["arena_wins"] += 1
            loser["arena_losses"] += 1
            winner["season_points"] += 15
            winner["gold"] += duel["wager"] * 2
            arenas.pop(duel_id)
            await self.config.guild(ctx.guild).arenas.set(arenas)
            await self._save_profile(
                ctx.guild.id,
                challenger_member.id,
                challenger,
                challenger_start,
            )
            await self._save_profile(
                ctx.guild.id,
                ctx.author.id,
                defender,
                defender_start,
            )
        await ctx.send(
            embed=discord.Embed(
                title="⚔️ Arena Result",
                description=(
                    f"**{winner_member.display_name}** defeats **{loser_member.display_name}**!\n"
                    f"Prize: **{self._money(winner, duel['wager'] * 2)}** • **15 season points**\n\n"
                    f"Power rating: {challenger_member.display_name} {challenger_power} "
                    f"vs. {ctx.author.display_name} {defender_power}"
                ),
                color=GOLD_COLOR,
            ),
        )

    @arena_group.command(name="decline")
    @commands.guild_only()
    async def arena_decline(self, ctx: commands.Context, duel_id: str) -> None:
        """Decline a pending challenge and refund its wager."""
        duel_id = duel_id.upper()
        async with self._guild_lock_for(ctx.guild.id):
            arenas = await self.config.guild(ctx.guild).arenas()
            duel = arenas.get(duel_id)
            if not duel or duel["opponent"] != ctx.author.id:
                await ctx.send("That is not a pending challenge addressed to you.")
                return
            challenger_member = ctx.guild.get_member(int(duel["challenger"]))
            if challenger_member:
                challenger = await self._get_profile(ctx.guild.id, challenger_member.id)
                starting_gold = challenger["gold"]
                challenger["gold"] += duel["wager"]
                await self._save_profile(
                    ctx.guild.id,
                    challenger_member.id,
                    challenger,
                    starting_gold,
                )
            arenas.pop(duel_id)
            await self.config.guild(ctx.guild).arenas.set(arenas)
        await ctx.send("The challenge is declined and its wager refunded.")

    @arena_group.command(name="cancel")
    @commands.guild_only()
    async def arena_cancel(self, ctx: commands.Context, duel_id: str) -> None:
        """Cancel your pending challenge and recover its escrowed wager."""
        duel_id = duel_id.upper()
        async with self._guild_lock_for(ctx.guild.id):
            arenas = await self.config.guild(ctx.guild).arenas()
            duel = arenas.get(duel_id)
            if not duel or duel["challenger"] != ctx.author.id:
                await ctx.send("That is not one of your pending challenges.")
                return
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["gold"] += duel["wager"]
            arenas.pop(duel_id)
            await self.config.guild(ctx.guild).arenas.set(arenas)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send("The challenge is cancelled and its wager refunded.")

    @deepdelve.group(name="endgame", invoke_without_command=True)
    @commands.guild_only()
    async def endgame_group(self, ctx: commands.Context) -> None:
        """Enter rifts, daily dungeons, seasons, ascension, and world raids."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        season = current_season()
        embed = discord.Embed(
            title=f"🌌 {season['name']}",
            description=(
                f"**Season:** {season['id']}\n"
                f"**Season Points:** {profile['season_points']}\n"
                f"**Ascensions:** {profile['ascensions']}\n"
                f"**Prestige:** {profile['prestige']}\n"
                f"**Challenge Rifts:** {profile['rifts_completed']}\n"
                f"**Hardcore:** {'Dead' if profile['hardcore_dead'] else 'Active' if profile['hardcore'] else 'Off'}"
            ),
            color=0x4A235A,
        )
        await ctx.send(embed=embed)

    async def _start_challenge(
        self,
        ctx: commands.Context,
        profile: dict[str, Any],
        *,
        kind: str,
        challenge_floor: int,
        waves: int,
        multiplier: float,
        challenge_date: str = "",
        name: str,
        seed: int = 0,
    ) -> None:
        if profile["encounter"] or profile["choice"] or profile.get("active_puzzle") or profile.get("rift_state"):
            await ctx.send("Finish your current encounter before opening another challenge.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            if profile["encounter"] or profile["choice"] or profile.get("active_puzzle") or profile.get("rift_state"):
                await ctx.send("Finish your current encounter before opening another challenge.")
                return
            starting_gold = profile["gold"]
            profile["rift_state"] = {
                "kind": kind,
                "name": name,
                "wave": 0,
                "waves": waves,
                "challenge_floor": challenge_floor,
                "reward_multiplier": multiplier,
                "date": challenge_date,
                "seed": seed,
                "original_floor": profile["floor"],
                "original_rooms": profile["rooms_cleared"],
            }
            profile["floor"] = challenge_floor
            challenge_rng = random.Random(seed) if seed else random
            enemy = apply_affix(
                enemy_for_floor(challenge_floor, challenge_rng),
                challenge_floor + 10,
                challenge_rng,
            )
            enemy = self._apply_challenge_enemy_modifier(enemy, name, challenge_rng)
            enemy["name"] = f"Riftbound {enemy['name']}"
            profile["encounter"] = ensure_enemy_intent(enemy)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            embed=self._combat_embed(
                profile,
                f"🌀 **{name} — Wave 1/{waves}**\nReality seals behind you.",
            ),
            view=CombatView(self, ctx.author.id, profile),
        )

    @endgame_group.command(name="rift")
    @commands.guild_only()
    async def endgame_rift(self, ctx: commands.Context, difficulty: int = 1) -> None:
        """Open a five-wave challenge rift at difficulty 1–10."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["deepest_floor"] < 10:
            await ctx.send("Challenge rifts unlock after reaching floor 10.")
            return
        if not 1 <= difficulty <= 10:
            await ctx.send("Difficulty must be between 1 and 10.")
            return
        challenge_floor = profile["deepest_floor"] + difficulty * 2
        await self._start_challenge(
            ctx,
            profile,
            kind="rift",
            challenge_floor=challenge_floor,
            waves=5,
            multiplier=1 + difficulty * 0.15,
            name=f"Rift Tier {difficulty}",
        )

    @endgame_group.command(name="daily")
    @commands.guild_only()
    async def endgame_daily(self, ctx: commands.Context) -> None:
        """Enter the shared UTC daily dungeon."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        challenge = daily_dungeon()
        if profile["daily_date"] == challenge["date"]:
            await ctx.send("You have already completed today's daily dungeon.")
            return
        if profile["deepest_floor"] < 5:
            await ctx.send("Daily dungeons unlock after reaching floor 5.")
            return
        challenge_floor = scaled_daily_floor(challenge["floor"], profile["deepest_floor"])
        await self._start_challenge(
            ctx,
            profile,
            kind="daily",
            challenge_floor=challenge_floor,
            waves=3,
            multiplier=challenge["reward_multiplier"],
            challenge_date=challenge["date"],
            name=f"Daily: {challenge['name']}",
            seed=challenge["seed"],
        )

    @endgame_group.command(name="hardcore")
    @commands.guild_only()
    async def endgame_hardcore(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable irreversible Hardcore death before beginning an adventure."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["kills"] or profile["deepest_floor"] > 1:
            await ctx.send("Hardcore mode can only be changed before the first kill.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            profile["hardcore"] = enabled
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            "☠️ Hardcore mode enabled. **Combat death permanently seals this character.**"
            if enabled
            else "Hardcore mode disabled.",
        )

    @endgame_group.command(name="ascend")
    @commands.guild_only()
    async def endgame_ascend(self, ctx: commands.Context, confirm: bool = False) -> None:
        """Reset combat progression for permanent prestige after floor 20."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile["deepest_floor"] < 20 or profile["bosses"] < 4:
            await ctx.send("Ascension requires floor 20 and at least four defeated bosses.")
            return
        if profile["encounter"] or profile["choice"] or profile.get("active_puzzle") or profile.get("rift_state"):
            await ctx.send("Finish or leave your current encounter before ascending.")
            return
        if not confirm:
            await ctx.send(
                "Ascension resets level, XP, floor, attributes, talents, inventory, equipment, "
                "materials, and combat records. Lore, codex, titles, currency, achievements, "
                "reputation, and social memberships remain.\n"
                "Run `/deepdelve endgame ascend confirm:true` to proceed.",
            )
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            if profile["encounter"] or profile["choice"] or profile.get("active_puzzle") or profile.get("rift_state"):
                await ctx.send("Your adventure state changed. Finish it before ascending.")
                return
            starting_gold = profile["gold"]
            details = GAME_CLASSES[profile["class_key"]]
            profile.update(
                {
                    "level": 1,
                    "xp": 0,
                    "hp": details["max_hp"],
                    "mana": details["max_mana"],
                    "floor": 1,
                    "rooms_cleared": 0,
                    "deepest_floor": 1,
                    "encounter": {},
                    "choice": {},
                    "active_puzzle": {},
                    "status": {},
                    "inventory": [],
                    "stash": [],
                    "loadouts": {},
                    "favorite_items": [],
                    "equipment": {"weapon": None, "armor": None, "charm": None},
                    "consumables": {},
                    "materials": dict.fromkeys(MATERIALS, 0),
                    "kills": 0,
                    "bosses": 0,
                    "attributes": dict.fromkeys(profile["attributes"], 0),
                    "attribute_points": 7,
                    "talents": {},
                    "talent_points": 2,
                    "skill_cooldowns": {},
                    "combat_flags": {},
                    "free_revive": True,
                    "subclass": "",
                    "map_nodes": [],
                    "floor_mutator": floor_mutator(1, profile["ascensions"] + 1),
                    "boss_relic_pity": 0,
                    "loot_pity": 0,
                    "conviction_fatigue": 0,
                    "set_pity": 0,
                    "rift_state": {},
                    "ascensions": profile["ascensions"] + 1,
                    "prestige": profile["prestige"] + 1,
                },
            )
            background = BACKGROUNDS.get(profile.get("background", ""))
            if background:
                for attribute, amount in background["attributes"].items():
                    profile["attributes"][attribute] += amount
            starter_choice = profile.get("starter_choice", "")
            if starter_choice in starter_options(profile["class_key"]):
                profile["equipment"]["weapon"] = create_starter_item(
                    profile["class_key"],
                    starter_choice,
                )
            available = [blessing["name"] for blessing in BLESSINGS if blessing["name"] not in profile["blessings"]]
            if available:
                profile["blessings"].append(random.choice(available))
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            f"🌠 **ASCENSION {profile['ascensions']}** — The Deep remembers you. "
            "Permanent prestige strengthens every future incarnation.",
        )

    @endgame_group.command(name="season")
    @commands.guild_only()
    async def endgame_season(self, ctx: commands.Context) -> None:
        """View the current seasonal leaderboard."""
        if not await self._channel_allowed(ctx):
            return
        season = current_season()
        all_members = await self.config.all_members(ctx.guild)
        rankings = sorted(
            (
                (member_id, data)
                for member_id, data in all_members.items()
                if data.get("created") and data.get("season_id") == season["id"]
            ),
            key=lambda entry: int(entry[1].get("season_points", 0)),
            reverse=True,
        )[:10]
        lines = [
            f"`#{index}` <@{member_id}> — **{data.get('season_points', 0)} points**"
            for index, (member_id, data) in enumerate(rankings, start=1)
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"🏆 {season['name']}",
                description="\n".join(lines) or "No seasonal points have been earned.",
                color=GOLD_COLOR,
            ),
        )

    @endgame_group.command(name="worldboss")
    @commands.guild_only()
    async def endgame_worldboss(self, ctx: commands.Context) -> None:
        """Summon or inspect the persistent server-wide world boss."""
        if not await self._channel_allowed(ctx):
            return
        async with self._guild_lock_for(ctx.guild.id):
            record = await self.config.guild(ctx.guild).world_boss()
            if not record:
                defeated_at = await self.config.guild(ctx.guild).world_boss_defeated_at()
                if defeated_at:
                    elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(defeated_at)
                    if elapsed.total_seconds() < 86400:
                        remaining = round((86400 - elapsed.total_seconds()) / 3600, 1)
                        await ctx.send(
                            f"Lastlight is safe. The next world threat may emerge in **{remaining} hours**.",
                        )
                        return
                all_members = await self.config.all_members(ctx.guild)
                delver_count = max(1, sum(1 for data in all_members.values() if data.get("created")))
                maximum = 2500 + delver_count * 650
                season = current_season()
                record = {
                    "name": "Nhal, Eater of Seasons",
                    "emoji": "🌌",
                    "description": (f"Drawn by {season['name']}, a shadow large enough to cover Lastlight descends."),
                    "hp": maximum,
                    "max_hp": maximum,
                    "contributions": {},
                    "last_attacks": {},
                    "spawned": datetime.now(timezone.utc).isoformat(),
                }
                await self.config.guild(ctx.guild).world_boss.set(record)
        await ctx.send(embed=self._world_boss_embed(record), view=WorldBossView(self))

    @deepdelve.group(name="chronicle", aliases=["solo"], invoke_without_command=True)
    @commands.guild_only()
    async def chronicle_group(self, ctx: commands.Context) -> None:
        """Explore the campaign, companions, professions, puzzles, events, and town."""
        profile = await self._require_character(ctx)
        if profile:
            await self._send_art_embed(
                ctx,
                self._chronicle_embed(profile, ctx.guild.id),
                "chronicle-campaign.png",
            )

    @chronicle_group.command(name="rumor", aliases=["hunt"])
    @commands.guild_only()
    async def chronicle_rumor(self, ctx: commands.Context) -> None:
        """View your active personal hunt."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        rumor = profile.get("active_rumor") or {}
        if not rumor:
            await ctx.send("🗺️ No rumor is active. Listen for wanderers during exploration.")
            return
        await ctx.send(
            embed=discord.Embed(
                title=f"🗺️ {rumor['name']}",
                description=(
                    f"{rumor.get('description', 'Hunt creatures within the marked region.')}\n\n"
                    f"**Progress:** {rumor['progress']}/{rumor['target']}\n"
                    f"**Reward:** {self._money(profile, rumor['reward_gold'])} + "
                    f"{rumor['reward_shards']} shards + regional pattern"
                ),
                color=EMBED_COLOR,
            ),
        )

    @chronicle_group.command(name="bestiary", aliases=["monsters"])
    @commands.guild_only()
    async def chronicle_bestiary(self, ctx: commands.Context) -> None:
        """Review creatures observed, understood, and mastered."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        entries = sorted(
            profile.get("bestiary", {}).values(),
            key=lambda entry: (-int(entry.get("mastery", 0)), -int(entry.get("kills", 0))),
        )
        mastery_names = ("Unstudied", "Observed", "Understood", "Mastered")
        sections: dict[str, list[str]] = {"boss": [], "miniboss": [], "creature": []}
        for entry in entries[:24]:
            variants = entry.get("affixes", {})
            variant_text = f" • {len(variants)} elite variant(s)" if variants else ""
            floor_text = (
                f"F{entry.get('min_floor', '?')}"
                if entry.get("min_floor") == entry.get("max_floor")
                else f"F{entry.get('min_floor', '?')}–{entry.get('max_floor', '?')}"
            )
            sections.setdefault(entry.get("kind", "creature"), []).append(
                f"**{entry['name']}** — {entry['kills']} kills • "
                f"{mastery_names[min(3, int(entry.get('mastery', 0)))]} • {floor_text}{variant_text}",
            )
        blocks = [
            f"**{heading}**\n" + "\n".join(sections[key])
            for key, heading in (
                ("boss", "👑 Bosses"),
                ("miniboss", "⚔️ Minibosses"),
                ("creature", "📖 Creatures"),
            )
            if sections.get(key)
        ]
        await ctx.send(
            embed=discord.Embed(
                title=f"📚 Bestiary — {len(entries)} creatures",
                description="\n\n".join(blocks) or "*No creature has yet been recorded.*",
                color=EMBED_COLOR,
            ),
        )

    @chronicle_group.command(name="recap", aliases=["legacy"])
    @commands.guild_only()
    async def chronicle_recap(self, ctx: commands.Context) -> None:
        """Read a personalized recap of your delver's legacy."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        await ctx.send(
            embed=discord.Embed(
                title=f"📖 The Chronicle of {profile['character_name']}",
                description="\n".join(ending_recap(profile)),
                color=GOLD_COLOR,
            ),
        )

    @chronicle_group.command(name="morality", aliases=["alignment"])
    @commands.guild_only()
    async def chronicle_morality(self, ctx: commands.Context) -> None:
        """View living Morality, convictions, transformation, and combat power."""
        profile = await self._require_character(ctx)
        if profile:
            await ctx.send(embed=self._morality_embed(profile))

    @chronicle_group.command(name="deeds")
    @commands.guild_only()
    async def chronicle_deeds(self, ctx: commands.Context) -> None:
        """Read the permanent moral record of your recent choices."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        deeds = profile.get("moral_deeds", [])
        lines = []
        for deed in reversed(deeds[-15:]):
            details = [f"{int(deed.get('morality', 0)):+d} Morality"]
            details.extend(f"{int(amount):+d} {conviction.title()}" for conviction, amount in deed.get("convictions", {}).items())
            lines.append(
                f"**Floor {deed.get('floor', '?')} — {deed['name']}**\n{' • '.join(details)}",
            )
        await ctx.send(
            embed=discord.Embed(
                title="⚖️ The Book of Deeds",
                description="\n\n".join(lines) or "*No deed has yet been judged.*",
                color=morality_path(profile)["color"],
            ),
        )

    @chronicle_group.command(name="tutorial")
    @commands.guild_only()
    async def chronicle_tutorial(self, ctx: commands.Context) -> None:
        """Read the interactive Delver's Primer."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        embed = self._tutorial_embed(profile)
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            current = await self._get_profile(ctx.guild.id, ctx.author.id)
            if not current.get("tutorial_complete"):
                step = int(current.get("tutorial_step", 0))
                if step >= 4:
                    current["tutorial_complete"] = True
                    current["gold"] += 75
                    embed.add_field(
                        name="Primer Reward",
                        value="🏆 Primer completed: **75 gold** awarded.",
                        inline=False,
                    )
                else:
                    current["tutorial_step"] = step + 1
                await self._save_profile(ctx.guild.id, ctx.author.id, current, profile["gold"])
        await ctx.send(embed=embed)

    @chronicle_group.command(name="campaign", aliases=["story"])
    @commands.guild_only()
    async def chronicle_campaign(self, ctx: commands.Context, action: str | None = None) -> None:
        """View or continue the branching five-chapter campaign."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        scene = campaign_scene(profile)
        narrative = None
        if action:
            action = action.lower().strip()
            if action == "continue":
                action = None
            async with self._lock_for(ctx.guild.id, ctx.author.id):
                profile = await self._get_profile(ctx.guild.id, ctx.author.id)
                starting_gold = profile["gold"]
                result = advance_campaign(profile, action)
                narrative = result["message"]
                if result["ok"]:
                    level_lines = self._apply_level_ups(profile)
                    award = self._award_achievements(profile)
                    extras = [*level_lines, award]
                    extras = [line for line in extras if line]
                    if extras:
                        narrative += "\n\n" + "\n".join(extras)
                    await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
            scene = campaign_scene(profile)
        view = None
        if not scene["complete"] and scene["available"]:
            if scene["at_choice"]:
                view = CampaignView(self, ctx.author.id, scene["chapter"]["choice"]["options"])
            else:
                view = CampaignContinueView(self, ctx.author.id)
        await self._send_art_embed(
            ctx,
            self._campaign_embed(profile, narrative),
            "chronicle-campaign.png",
            view=view,
        )

    @chronicle_group.command(name="puzzle", aliases=["riddle"])
    @commands.guild_only()
    async def chronicle_puzzle(self, ctx: commands.Context) -> None:
        """Resume a puzzle or view puzzle discoveries."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if profile.get("active_puzzle"):
            await ctx.send(
                embed=self._puzzle_embed(profile),
                view=PuzzleView(self, ctx.author.id, profile["active_puzzle"]),
            )
            return
        embed = discord.Embed(
            title="🧩 Riddles of the Deep",
            description=(
                "Puzzle chambers appear naturally while exploring. Wrong answers inflict damage; "
                "two failures seal the chamber. Professions, companions, town upgrades, and world events "
                "can improve their rewards."
            ),
            color=0x2980B9,
        )
        embed.add_field(
            name="Record",
            value=(
                f"Unique puzzles: **{len(profile.get('solved_puzzles', []))}/5**\n"
                f"Current streak: **{profile.get('puzzle_streak', 0)}**"
            ),
        )
        await ctx.send(embed=embed)

    @chronicle_group.command(name="companion", aliases=["pet"])
    @commands.guild_only()
    async def chronicle_companion(self, ctx: commands.Context, name: str | None = None) -> None:
        """View companions or activate one you have discovered."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if name:
            key = name.lower().strip()
            if key not in profile.get("companions", {}):
                await ctx.send("You have not discovered that companion. Their keys are shown in the companion journal.")
                return
            async with self._lock_for(ctx.guild.id, ctx.author.id):
                profile = await self._get_profile(ctx.guild.id, ctx.author.id)
                starting_gold = profile["gold"]
                if profile.get("active_companion") == key:
                    await ctx.send(f"{COMPANIONS[key]['emoji']} **{COMPANIONS[key]['name']}** is already accompanying you.")
                    return
                profile["active_companion"] = key
                await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
            definition = COMPANIONS[key]
            embed = self._companion_embed(profile)
            embed.description = (
                f"{definition['emoji']} **{definition['name']} joins your expedition.**\n"
                f"*{definition['passive']}*\n\n" + embed.description
            )
            await self._send_art_embed(ctx, embed, "companions.png")
            return
        await self._send_art_embed(ctx, self._companion_embed(profile), "companions.png")

    @chronicle_group.command(name="profession", aliases=["job"])
    @commands.guild_only()
    async def chronicle_profession(self, ctx: commands.Context, name: str | None = None) -> None:
        """View, choose, or change your persistent profession."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not name:
            await ctx.send(embed=self._profession_embed(profile))
            return
        key = name.lower().replace(" ", "_").strip()
        if key not in PROFESSIONS:
            await ctx.send(f"Choose {humanize_list([f'`{entry}`' for entry in PROFESSIONS])}.")
            return
        current_key = profile.get("profession", {}).get("key", "")
        if current_key == key:
            await ctx.send(f"You are already a **{PROFESSIONS[key]['name']}**.")
            return
        cost = 0 if not current_key else 150 + int(profile["level"]) * 15
        if profile["gold"] < cost:
            await ctx.send(f"Changing professions costs **{self._money(profile, cost)}**.")
            return
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            current = profile.get("profession", {})
            if current.get("key"):
                profile["profession_mastery"][current["key"]] = {
                    "level": int(current.get("level", 1)),
                    "xp": int(current.get("xp", 0)),
                }
            restored = profile["profession_mastery"].get(key, {"level": 1, "xp": 0})
            profile["profession"] = {"key": key, **restored}
            profile["gold"] -= cost
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        definition = PROFESSIONS[key]
        await ctx.send(
            f"{definition['emoji']} You are now a **{definition['name']}**. "
            f"{'No fee for your first calling.' if not cost else f'Changing paths cost {self._money(profile, cost)}.'}",
        )

    @chronicle_group.command(name="gather")
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def chronicle_gather(self, ctx: commands.Context) -> None:
        """Use one of three daily profession gathering actions."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if not profile.get("profession", {}).get("key"):
            await ctx.send("Choose a profession first with `/deepdelve chronicle profession`.")
            return
        today = datetime.now(timezone.utc).date().isoformat()
        async with self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            if profile.get("gather_date") != today:
                profile["gather_date"] = today
                profile["gather_actions"] = 0
            if int(profile.get("gather_actions", 0)) >= 3:
                await ctx.send("You have used all **three** gathering actions for today. They reset at 00:00 UTC.")
                return
            if int(profile.get("turns", 0)) < 1:
                await ctx.send("Gathering costs **1 exploration energy**, but none remains.")
                return
            profile["turns"] -= 1
            result = gather(profile)
            profile["gather_actions"] += 1
            commission_lines = progress_commission(profile, "gather")
            quest_lines = progress_quests(profile, "recover")
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        text = (
            f"{result['emoji']} You gather **{result['amount']} {result['name']}** "
            f"({3 - profile['gather_actions']} daily actions remain)."
        )
        if result["potion"]:
            text += "\n⚗️ Your alchemical technique also produces **one potion**."
        if result["messages"]:
            text += "\n" + "\n".join(result["messages"])
        if commission_lines or quest_lines:
            text += "\n" + "\n".join([*commission_lines, *quest_lines])
        text += f"\n🧭 **-1 energy** • {profile['turns']} remains."
        await ctx.send(text)

    @chronicle_group.command(name="world", aliases=["event"])
    @commands.guild_only()
    async def chronicle_world(self, ctx: commands.Context) -> None:
        """Inspect today's server-specific dynamic world event."""
        if await self._channel_allowed(ctx):
            await ctx.send(embed=self._world_event_embed(ctx.guild.id))

    @chronicle_group.command(name="town")
    @commands.guild_only()
    async def chronicle_town(self, ctx: commands.Context) -> None:
        """View Lastlight's server-wide development."""
        profile = await self._require_character(ctx)
        if profile:
            town = await self.config.guild(ctx.guild).town()
            await self._send_art_embed(
                ctx,
                self._town_development_embed(profile, town),
                "lastlight-town.png",
            )

    @chronicle_group.command(name="contribute")
    @commands.guild_only()
    async def chronicle_contribute(self, ctx: commands.Context, amount: int) -> None:
        """Contribute character currency to Lastlight's shared treasury."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        if amount < 10:
            await ctx.send("The builders can only record contributions of at least **10**.")
            return
        async with self._guild_lock_for(ctx.guild.id), self._lock_for(ctx.guild.id, ctx.author.id):
            profile = await self._get_profile(ctx.guild.id, ctx.author.id)
            starting_gold = profile["gold"]
            if profile["gold"] < amount:
                await ctx.send(f"You only carry **{self._money(profile, profile['gold'])}**.")
                return
            town = await self.config.guild(ctx.guild).town()
            profile["gold"] -= amount
            profile["town_contribution"] += amount
            town["treasury"] = int(town.get("treasury", 0)) + amount
            contributors = town.setdefault("contributors", {})
            contributors[str(ctx.author.id)] = int(contributors.get(str(ctx.author.id), 0)) + amount
            await self.config.guild(ctx.guild).town.set(town)
            await self._save_profile(ctx.guild.id, ctx.author.id, profile, starting_gold)
        await ctx.send(
            embed=self._town_development_embed(profile, town),
            content=f"🏗️ {ctx.author.mention} contributes **{self._money(profile, amount)}** to Lastlight.",
        )

    @chronicle_group.command(name="townupgrade")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def chronicle_town_upgrade(self, ctx: commands.Context, building: str) -> None:
        """Spend shared treasury funds on a town building."""
        profile = await self._require_character(ctx)
        if not profile:
            return
        key = building.lower().replace(" ", "_").strip()
        async with self._guild_lock_for(ctx.guild.id):
            town = await self.config.guild(ctx.guild).town()
            result = upgrade_building(town, key)
            if result["ok"]:
                await self.config.guild(ctx.guild).town.set(town)
        if not result["ok"]:
            await ctx.send(result["message"])
            return
        await ctx.send(
            embed=self._town_development_embed(profile, town),
            content=(
                f"{result['building']['emoji']} **{result['building']['name']}** reaches "
                f"level **{result['level']}** for **{self._money(profile, result['cost'])}**."
            ),
        )

    @deepdelve.command(name="leaderboard", aliases=["top"])
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context, category: str = "depth") -> None:
        """View rankings for depth, level, kills, gold, or bosses."""
        if not await self._channel_allowed(ctx):
            return
        categories = {
            "depth": ("deepest_floor", "Deepest Floor", "🏰"),
            "level": ("level", "Level", "✨"),
            "kills": ("kills", "Enemies Defeated", "☠️"),
            "gold": ("gold", "Gold", "🪙"),
            "bosses": ("bosses", "Bosses Defeated", "🏆"),
        }
        category = category.lower()
        if category not in categories:
            await ctx.send(f"Choose a category: {humanize_list(list(categories))}.")
            return
        key, title, emoji = categories[category]
        all_members = await self.config.all_members(ctx.guild)
        rankings = [(member_id, data) for member_id, data in all_members.items() if data.get("created")]
        economy_mode = await self.config.guild(ctx.guild).economy_mode()
        if key == "gold" and economy_mode == "bank":
            title = await bank.get_currency_name(ctx.guild)
            for member_id, data in rankings:
                member = ctx.guild.get_member(int(member_id))
                if member:
                    data["gold"] = await bank.get_balance(member)
        rankings.sort(key=lambda entry: int(entry[1].get(key, 0)), reverse=True)
        if not rankings:
            await ctx.send("No delvers have entered the dungeon yet.")
            return
        lines = []
        medals = ("🥇", "🥈", "🥉")
        for position, (member_id, data) in enumerate(rankings[:10], start=1):
            member = ctx.guild.get_member(int(member_id))
            name = member.display_name if member else data.get("character_name", f"Delver {member_id}")
            marker = medals[position - 1] if position <= 3 else f"`#{position}`"
            lines.append(f"{marker} **{name}** — {emoji} **{data.get(key, 0)}**")
        embed = discord.Embed(
            title=f"{emoji} DeepDelve Leaderboard — {title}",
            description="\n".join(lines),
            color=GOLD_COLOR,
        )
        embed.set_footer(text=f"Use /deepdelve leaderboard category:{category}")
        await ctx.send(embed=embed)

    @deepdelve.command(name="retire")
    @commands.guild_only()
    async def retire(self, ctx: commands.Context) -> None:
        """Permanently delete your character and start over."""
        if not await self._channel_allowed(ctx):
            return
        profile = await self._get_profile(ctx.guild.id, ctx.author.id)
        if not profile["created"]:
            await ctx.send(embed=self._not_created_embed())
            return
        embed = discord.Embed(
            title="🪦 Retire this character?",
            description=(
                "This permanently deletes your levels, equipment, gold, achievements, and all other progress. "
                "**This cannot be undone.**"
            ),
            color=DANGER_COLOR,
        )
        await ctx.send(embed=embed, view=RetireConfirmView(self, ctx.author.id))

    @deepdelve.group(name="set", invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def deepdelve_set(self, ctx: commands.Context) -> None:
        """Configure DeepDelve for this server."""
        data = await self.config.guild(ctx.guild).all()
        channel = ctx.guild.get_channel(data["adventure_channel"])
        channel_text = channel.mention if channel else "Any channel"
        embed = discord.Embed(
            title="⚙️ DeepDelve Settings",
            color=EMBED_COLOR,
        )
        embed.add_field(name="Enabled", value="Yes" if data["enabled"] else "No")
        embed.add_field(name="Adventure Channel", value=channel_text)
        embed.add_field(name="Daily Turns", value=str(data["daily_turns"]))
        embed.add_field(name="Difficulty", value=f"{float(data.get('content_multiplier', 1.0)):.2f}×")
        embed.add_field(
            name="Economy",
            value=(
                "Red bank — all game transactions use the server economy"
                if data["economy_mode"] == "bank"
                else "Internal — isolated dungeon gold"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @deepdelve_set.command(name="enabled")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def set_enabled(self, ctx: commands.Context, enabled: bool) -> None:
        """Enable or disable gameplay in this server."""
        await self.config.guild(ctx.guild).enabled.set(enabled)
        await ctx.send(f"DeepDelve is now **{'enabled' if enabled else 'disabled'}**.")

    @deepdelve_set.command(name="channel")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def set_channel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Restrict gameplay to one channel, or omit the channel to clear the restriction."""
        await self.config.guild(ctx.guild).adventure_channel.set(channel.id if channel else 0)
        if channel:
            await ctx.send(f"DeepDelve adventures are now restricted to {channel.mention}.")
        else:
            await ctx.send("DeepDelve adventures may now be played in any channel.")

    @deepdelve_set.command(name="turns")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def set_turns(self, ctx: commands.Context, turns: int) -> None:
        """Set the number of daily exploration turns (5–100)."""
        if not 5 <= turns <= 100:
            await ctx.send("Daily turns must be between 5 and 100.")
            return
        await self.config.guild(ctx.guild).daily_turns.set(turns)
        await ctx.send(f"New UTC days will grant each delver **{turns} turns**.")

    @deepdelve_set.command(name="difficulty")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def set_difficulty(self, ctx: commands.Context, multiplier: float) -> None:
        """Set enemy scaling from 0.75× to 2.00×."""
        if not 0.75 <= multiplier <= 2.0:
            await ctx.send("Difficulty must be between **0.75** and **2.00**.")
            return
        await self.config.guild(ctx.guild).content_multiplier.set(round(multiplier, 2))
        await ctx.send(
            f"DeepDelve enemy health, attack, and defense now scale at **{multiplier:.2f}×**. "
            "Higher difficulty also modestly increases rewards.",
        )

    @deepdelve_set.command(name="economy")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def set_economy(self, ctx: commands.Context, mode: str) -> None:
        """Choose `internal` dungeon gold or Red's shared `bank` economy."""
        mode = mode.lower().strip()
        if mode not in {"internal", "bank"}:
            await ctx.send("Economy mode must be `internal` or `bank`.")
            return
        await self.config.guild(ctx.guild).economy_mode.set(mode)
        if mode == "bank":
            currency = await bank.get_currency_name(ctx.guild)
            await ctx.send(
                f"DeepDelve now uses Red's bank and **{currency}**. All rewards, purchases, "
                "sales, penalties, achievements, crafting, and rankings affect real bank balances. "
                "Existing internal dungeon gold is retained but inactive.",
            )
        else:
            await ctx.send(
                "DeepDelve now uses its isolated internal gold. The most recently cached character "
                "balance becomes each character's internal balance; Red bank balances are no longer changed.",
            )

    @deepdelve_set.command(name="resetuser")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def reset_user(self, ctx: commands.Context, member: discord.Member) -> None:
        """Delete a member's DeepDelve profile."""
        await self.config.member(member).clear()
        await ctx.send(f"Deleted {member.mention}'s DeepDelve character data.")

    async def red_get_data_for_user(self, *, user_id: int) -> dict[str, io.BytesIO]:
        """Export a user's DeepDelve profiles for Red's data request API."""
        payload: dict[str, Any] = {"profiles": {}, "social_records": {}}
        all_profiles = await self.config.all_members()
        for guild_id, members in all_profiles.items():
            data = members.get(user_id)
            if data and data.get("created"):
                payload["profiles"][str(guild_id)] = data
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            social: dict[str, Any] = {}
            parties = {code: record for code, record in data.get("parties", {}).items() if user_id in record.get("members", [])}
            auctions = {
                code: record for code, record in data.get("auctions", {}).items() if int(record.get("seller", 0)) == user_id
            }
            player_guilds = {
                code: record for code, record in data.get("player_guilds", {}).items() if user_id in record.get("members", [])
            }
            arenas = {
                code: record
                for code, record in data.get("arenas", {}).items()
                if user_id in {int(record.get("challenger", 0)), int(record.get("opponent", 0))}
            }
            if parties:
                social["parties"] = parties
            if auctions:
                social["auctions"] = auctions
            if player_guilds:
                social["player_guilds"] = player_guilds
            if arenas:
                social["arenas"] = arenas
            world_boss = data.get("world_boss", {})
            if str(user_id) in world_boss.get("contributions", {}):
                social["world_boss"] = {
                    "damage": world_boss["contributions"][str(user_id)],
                    "last_attack": world_boss.get("last_attacks", {}).get(str(user_id)),
                }
            firsts = {
                boss: record for boss, record in data.get("server_firsts", {}).items() if int(record.get("user_id", 0)) == user_id
            }
            if firsts:
                social["server_firsts"] = firsts
            town = data.get("town", {})
            contribution = int(town.get("contributors", {}).get(str(user_id), 0))
            if contribution:
                social["town_contribution"] = contribution
            if social:
                payload["social_records"][str(guild_id)] = social
        if not payload["profiles"] and not payload["social_records"]:
            return {}
        serialized = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        return {"deepdelve.json": io.BytesIO(serialized)}

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Delete all character data belonging to a Discord user."""
        del requester
        all_guilds = await self.config.all_guilds()
        for guild_id, data in all_guilds.items():
            guild_proxy = self.config.guild_from_id(guild_id)
            parties = data.get("parties", {})
            for code, record in list(parties.items()):
                if user_id not in record.get("members", []):
                    continue
                record["members"] = [member_id for member_id in record["members"] if member_id != user_id]
                if not record["members"]:
                    parties.pop(code)
                else:
                    if record.get("leader") == user_id:
                        record["leader"] = record["members"][0]
                    parties[code] = record
            auctions = {
                code: record for code, record in data.get("auctions", {}).items() if int(record.get("seller", 0)) != user_id
            }
            player_guilds = data.get("player_guilds", {})
            for code, record in list(player_guilds.items()):
                if user_id not in record.get("members", []):
                    continue
                record["members"] = [member_id for member_id in record["members"] if member_id != user_id]
                if not record["members"]:
                    player_guilds.pop(code)
                else:
                    if record.get("owner") == user_id:
                        record["owner"] = record["members"][0]
                    player_guilds[code] = record
            arenas = {
                code: record
                for code, record in data.get("arenas", {}).items()
                if user_id
                not in {
                    int(record.get("challenger", 0)),
                    int(record.get("opponent", 0)),
                }
            }
            world_boss = data.get("world_boss", {})
            world_boss.get("contributions", {}).pop(str(user_id), None)
            world_boss.get("last_attacks", {}).pop(str(user_id), None)
            town = data.get("town", {})
            town.get("contributors", {}).pop(str(user_id), None)
            firsts = {
                boss: record for boss, record in data.get("server_firsts", {}).items() if int(record.get("user_id", 0)) != user_id
            }
            with contextlib.suppress(Exception):
                await guild_proxy.parties.set(parties)
                await guild_proxy.auctions.set(auctions)
                await guild_proxy.player_guilds.set(player_guilds)
                await guild_proxy.arenas.set(arenas)
                await guild_proxy.world_boss.set(world_boss)
                await guild_proxy.server_firsts.set(firsts)
                await guild_proxy.town.set(town)
        all_profiles = await self.config.all_members()
        for guild_id, members in all_profiles.items():
            if user_id not in members:
                continue
            with contextlib.suppress(Exception):
                await self.config.member_from_ids(guild_id, user_id).clear()
