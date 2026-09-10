"""Component-free TicketHub intake and controls using the same ticket services."""

from __future__ import annotations

import asyncio
import contextlib

import discord
from redbot.core import commands

CHOICE_EMOJIS = tuple(chr(0x1F1E6 + index) for index in range(20))
CONTROL_REACTIONS = {
    "✅": "claim",
    "🙋": "unclaim",
    "🔒": "lock",
    "🔓": "unlock",
    "❌": "close",
    "👐": "reopen",
    "📄": "transcript",
    "🗑️": "delete",
    "➕": "addmember",
    "➖": "removemember",
}


class AlternativeInteractions:
    """DM questionnaires and persistent raw-reaction routing."""

    @staticmethod
    def _parse_interaction_mode(value, *, form=False):
        value = str(value).lower().strip()
        allowed = {"modal", "text", "reaction"} if form else {"buttons", "text", "reaction"}
        if value not in allowed:
            raise commands.BadArgument("Choose " + ", ".join(sorted(allowed)) + ".")
        return value

    async def _command_hint(self, guild):
        prefixes = await self.bot.get_valid_prefixes(guild)
        prefix = next((p for p in prefixes if not p.startswith("<@")), prefixes[0])
        return f"{prefix}{self._prefix_root()}"

    def _check_reaction_channel(self, channel):
        if not self.bot.intents.reactions:
            raise commands.BadArgument("Enable the bot's reactions intent before selecting reaction mode.")
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.add_reactions or not permissions.read_message_history:
            raise commands.BadArgument("I need Add Reactions and Read Message History in the panel channel.")

    @staticmethod
    def _form_answer(field, value):
        value = value.strip()
        if value.lower() == "cancel":
            raise commands.CommandError("Ticket questionnaire cancelled.")
        if value.lower() == "skip":
            if field.get("required", True):
                raise ValueError("This question is required.")
            return ""
        if value.lower() == "default" and field.get("default"):
            value = str(field["default"])
        kind = field.get("type", "text")
        choices = field.get("choices", []) if kind == "choice" else ["Yes", "No"] if kind == "boolean" else []
        if choices:
            if value.isdigit() and 1 <= int(value) <= len(choices):
                value = choices[int(value) - 1]
            match = next((choice for choice in choices if choice.casefold() == value.casefold()), None)
            if match is None:
                raise ValueError("Reply with a listed choice or its number.")
            return match
        minimum = field.get("min_length") or (1 if field.get("required", True) else 0)
        maximum = field.get("max_length") or 4000
        if not minimum <= len(value) <= maximum:
            raise ValueError(f"Use between {minimum} and {maximum} characters.")
        return value

    async def _ask_dm(self, member, field, mode="text"):
        dm = await member.create_dm()
        choices = (
            field.get("choices", [])
            if field.get("type") == "choice"
            else (["Yes", "No"] if field.get("type") == "boolean" else [])
        )
        use_reactions = mode == "reaction" and 0 < len(choices) <= len(CHOICE_EMOJIS)
        lines = [str(field["label"]), str(field.get("placeholder") or "")]
        lines.extend(f"{CHOICE_EMOJIS[i] if use_reactions else i + 1} — {choice}" for i, choice in enumerate(choices))
        lines.append("Reply within 3 minutes. Type cancel to stop; skip skips optional questions.")
        if field.get("default"):
            lines.append(f"Type default to use: {field['default']}")
        prompt = await dm.send(
            embed=discord.Embed(description="\n".join(lines)[:4096]), allowed_mentions=discord.AllowedMentions.none()
        )
        tasks = []
        try:
            tasks.append(
                asyncio.create_task(
                    self.bot.wait_for(
                        "message",
                        check=lambda m: m.author.id == member.id and m.channel.id == dm.id and m.id > prompt.id,
                        timeout=180,
                    )
                )
            )
            if use_reactions:
                tasks.append(
                    asyncio.create_task(
                        self.bot.wait_for(
                            "raw_reaction_add",
                            check=lambda p: (
                                p.user_id == member.id
                                and p.message_id == prompt.id
                                and str(p.emoji) in CHOICE_EMOJIS[: len(choices)]
                            ),
                            timeout=180,
                        )
                    )
                )
                # Register listeners before seeding reactions so a fast reply is not lost.
                await asyncio.sleep(0)
                for emoji in CHOICE_EMOJIS[: len(choices)]:
                    await prompt.add_reaction(emoji)
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            result = next(iter(done)).result()
            value = result.content if hasattr(result, "content") else choices[CHOICE_EMOJIS.index(str(result.emoji))]
            return self._form_answer(field, value)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _open_without_components(self, guild, member, profile_name, *, reason=None, panel_label=None):
        if member.id in self._conversation_tasks:
            raise commands.CommandError("Finish or cancel your existing TicketHub DM conversation first.")
        self._conversation_tasks[member.id] = asyncio.current_task()
        try:
            profile_name, profile = await self._validate_ticket_open_request(guild, member, profile_name)
            answers = []
            for field in profile.get("creating_modal") or []:
                while True:
                    try:
                        answer = await self._ask_dm(member, field, profile.get("form_mode", "text"))
                        break
                    except ValueError as error:
                        await member.send(str(error))
                if answer:
                    answers.append({"label": field["label"], "value": answer})
            if len(answers) == 1 and answers[0]["label"].lower() == "reason":
                reason = answers[0]["value"][:1000]
            return await self._create_ticket(
                guild, member, profile_name, reason=reason or "Opened by request.", form_answers=answers, panel_label=panel_label
            )
        except asyncio.TimeoutError as error:
            raise commands.CommandError("Questionnaire timed out. Start again to open a ticket.") from error
        except discord.HTTPException as error:
            raise commands.CommandError(
                "I could not complete the DM questionnaire. Enable DMs from this server and try again."
            ) from error
        finally:
            self._conversation_tasks.pop(member.id, None)

    async def _alternative_panel(self, message, style, options):
        embeds = [e for e in message.embeds if e.footer.text != "TicketHub interaction options"]
        if style not in {"text", "reaction"}:
            if len(embeds) != len(message.embeds):
                await message.edit(embeds=embeds)
            return
        if style == "reaction" and len(options) > 20:
            raise commands.BadArgument("Reaction panels support at most 20 options. Use text or dropdown for more.")
        root = await self._command_hint(message.guild)
        lines = [
            f"{CHOICE_EMOJIS[i] + ' ' if style == 'reaction' else ''}`{root} open {option['profile']}` — {option['label']}"
            for i, option in enumerate(options)
        ]
        embed = discord.Embed(title="Open a ticket", description="\n".join(lines)[:4096])
        # Keep the original message content and embeds; replace only our own instruction card.
        if len(embeds) >= 10:
            raise commands.BadArgument("This message already has 10 embeds; make room for ticket instructions first.")
        embed.set_footer(text="TicketHub interaction options")
        await message.edit(embeds=[*embeds, embed], view=None)
        if style == "reaction":
            for emoji in CHOICE_EMOJIS[: len(options)]:
                await message.add_reaction(emoji)

    async def _alternative_controls(self, message, profile, record):
        mode = profile.get("control_mode", "buttons")
        if mode == "buttons":
            return
        root = await self._command_hint(message.guild)
        lines = [f"{emoji if mode == 'reaction' else '•'} `{root} {action}`" for emoji, action in CONTROL_REACTIONS.items()]
        lines.append("Member commands take a member mention or ID. Close/reopen commands accept a reason.")
        embed = self._ticket_embed(message.guild, record, profile)
        embed.add_field(name="Ticket controls", value="\n".join(lines), inline=False)
        await message.edit(embed=embed, view=None)
        if mode == "reaction":
            for emoji in CONTROL_REACTIONS:
                await message.add_reaction(emoji)
        pending = record.get("pending_close")
        if pending:
            confirmation = await self._fetch_close_confirmation_message(message.guild, record, pending)
            if confirmation:
                await confirmation.edit(
                    content=f"Use `{root} confirmclose` or `{root} cancelclose`."
                    + (" React ✅ to close or ❌ to cancel." if mode == "reaction" else ""),
                    view=None,
                )
                if mode == "reaction":
                    await confirmation.add_reaction("✅")
                    await confirmation.add_reaction("❌")

    async def _confirm_without_components(self, guild, record, member, confirmed):
        pending = record.get("pending_close")
        if not pending:
            raise commands.CommandError("This close confirmation is no longer active.")
        profile = await self._get_profile(guild, record["profile"])
        if member.id not in {int(record["owner_id"]), int(pending["requested_by"])} and not self._is_support_member(
            member, profile
        ):
            raise commands.CommandError("Only the ticket opener, close requester, or support staff can use this.")
        message = await self._fetch_close_confirmation_message(guild, record, pending)
        await self._resolve_close_confirmation(
            guild, int(record["id"]), member, confirmed=confirmed, expected_expires_at=float(pending["expires_at"])
        )
        if message:
            with contextlib.suppress(discord.HTTPException):
                await message.edit(content="Ticket closed." if confirmed else "Close cancelled.", embed=None, view=None)

    async def _reaction_action(self, guild, record, member, action):
        profile = await self._get_profile(guild, record["profile"])
        if action in {"addmember", "removemember"}:
            if not self._can_manage_ticket_members(member, record, profile, action="add" if action == "addmember" else "remove"):
                raise commands.CommandError("You cannot manage this ticket's members.")
            if member.id in self._conversation_tasks:
                raise commands.CommandError("Finish your existing TicketHub DM conversation first.")
            self._conversation_tasks[member.id] = asyncio.current_task()
            try:
                value = await self._ask_dm(member, {"label": "Reply with the member's numeric ID or mention.", "required": True})
                target = guild.get_member(int(value.strip("<@!>")))
                if target is None:
                    raise commands.CommandError("That member is not in this server.")
                method = self._add_ticket_member if action == "addmember" else self._remove_ticket_member
                record = await self._get_ticket_record_by_id(guild, int(record["id"]))
                await method(guild, record, member, target)
            finally:
                self._conversation_tasks.pop(member.id, None)
        elif action in {"close", "reopen"}:
            await self._lifecycle_without_modal(guild, record, member, action)
        elif action == "transcript":
            if member.id != int(record["owner_id"]) and not self._is_support_member(member, profile):
                raise commands.CommandError("Only the ticket owner or support staff can generate transcripts.")
            await self._send_transcript_bundle(guild, record, profile, requested_by=member)
        else:
            method = {
                "claim": self._claim_ticket,
                "unclaim": self._unclaim_ticket,
                "lock": self._lock_ticket,
                "unlock": self._unlock_ticket,
                "reopen": self._reopen_ticket,
                "delete": self._delete_ticket_channel,
            }[action]
            await method(guild, record, member)

    async def _lifecycle_without_modal(self, guild, record, member, action):
        validator = self._validate_close_request if action == "close" else self._validate_reopen_request
        await validator(guild, record, member)
        if member.id in self._conversation_tasks:
            raise commands.CommandError("Finish your existing TicketHub DM conversation first.")
        self._conversation_tasks[member.id] = asyncio.current_task()
        try:
            reason = await self._ask_dm(
                member,
                {
                    "label": f"Reason to {action} ticket #{record['id']} (type skip to omit).",
                    "required": False,
                    "max_length": 1000,
                },
            )
            record = await self._get_ticket_record_by_id(guild, int(record["id"]))
            if action == "close":
                await self._start_close_confirmation(guild, record, member, reason)
            else:
                await self._reopen_ticket(guild, record, member, reason=reason)
        finally:
            self._conversation_tasks.pop(member.id, None)

    async def _route_ticket_reaction(self, payload):
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        member = guild.get_member(payload.user_id) if guild else None
        if member is None or member.bot or await self.bot.cog_disabled_in_guild(self, guild):
            return
        if not await self.bot.allowed_by_whitelist_blacklist(member):
            return
        channel = guild.get_channel_or_thread(payload.channel_id)
        if channel is None or not channel.permissions_for(member).view_channel:
            return
        emoji = str(payload.emoji)
        try:
            profiles = await self._get_profiles(guild)
            for name, profile in profiles.items():
                if (
                    profile.get("panel_style") == "reaction"
                    and profile.get("panel_message_id") == payload.message_id
                    and profile.get("panel_channel_id") == payload.channel_id
                    and emoji == CHOICE_EMOJIS[0]
                ):
                    _record, ticket = await self._open_without_components(guild, member, name)
                    await member.send(f"Ticket opened: {ticket.mention}")
                    return
            panels = await self.config.guild(guild).multi_panels()
            panel = panels.get(str(payload.message_id))
            if panel and panel.get("style") == "reaction" and panel.get("channel_id") == payload.channel_id:
                options = panel.get("options", [])
                if emoji in CHOICE_EMOJIS[: len(options)]:
                    option = options[CHOICE_EMOJIS.index(emoji)]
                    _record, ticket = await self._open_without_components(
                        guild, member, option["profile"], panel_label=option["label"]
                    )
                    await member.send(f"Ticket opened: {ticket.mention}")
                return
            tickets = await self.config.guild(guild).tickets()
            for record in tickets.values():
                if int(record.get("channel_id") or 0) != payload.channel_id:
                    continue
                profile = profiles.get(record["profile"], {})
                pending = record.get("pending_close") or {}
                if (
                    pending.get("message_id") == payload.message_id
                    and profile.get("control_mode") == "reaction"
                    and emoji in {"✅", "❌"}
                ):
                    await self._confirm_without_components(guild, record, member, emoji == "✅")
                    return
                if (
                    record.get("message_id") == payload.message_id
                    and profile.get("control_mode") == "reaction"
                    and emoji in CONTROL_REACTIONS
                ):
                    await self._reaction_action(guild, record, member, CONTROL_REACTIONS[emoji])
                    return
        except (commands.CommandError, discord.HTTPException, ValueError, asyncio.TimeoutError) as error:
            with contextlib.suppress(discord.HTTPException):
                await member.send(f"TicketHub: {error}", allowed_mentions=discord.AllowedMentions.none())
