"""Confirmation controls for generated CommandHub setup plans."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from commandhub.suggestions import SuggestionPlan

log = logging.getLogger("red.taakoscogs.commandhub")


class PlanConfirmationView(discord.ui.View):
    def __init__(self, cog: Any, guild_id: int, owner_id: int, plan: SuggestionPlan) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.plan = plan
        self.message: Any = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Only the administrator who requested this preview can apply it.", ephemeral=True)
        return False

    @discord.ui.button(label="Apply plan", style=discord.ButtonStyle.success)
    async def apply(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self.cog.can_manage_interaction(interaction):
            await interaction.response.send_message("Manage Server is required to apply this plan.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            result = await self.cog.apply_suggestion_plan_service(self.guild_id, self.plan)
        except ValueError as exc:
            await interaction.edit_original_response(content=str(exc), embed=None, view=None)
            self.stop()
            return
        except Exception:
            log.exception("Failed to apply a CommandHub setup plan in guild %d.", self.guild_id)
            await interaction.edit_original_response(
                content="The plan could not be applied. Check the bot logs for details.",
                embed=None,
                view=None,
            )
            self.stop()
            return
        self.stop()
        await interaction.edit_original_response(
            content=(
                f"Plan applied: {result['commands_added']} command(s) added across "
                f"{result['hubs_changed']} hub(s); {result['duplicates']} existing assignment(s) skipped."
            ),
            embed=None,
            view=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Setup plan cancelled. Nothing was changed.", embed=None, view=None)
