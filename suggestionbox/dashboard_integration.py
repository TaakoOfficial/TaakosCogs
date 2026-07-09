"""Red-Web-Dashboard integration for SuggestionBox."""

from __future__ import annotations

import contextlib
import html
import logging
import typing

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.suggestionbox.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for SuggestionBox."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register SuggestionBox as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure SuggestionBox settings, records, review states, and threads.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> typing.Dict[str, typing.Any]:
        """Render and process the SuggestionBox dashboard page."""
        member, can_manage = await self._dashboard_member_can_manage(user, guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications = []
        form_data = self._dashboard_form_data(kwargs)

        if kwargs.get("method", "GET") == "POST":
            action = self._dash_value(form_data, "action")
            try:
                messages = await self._dashboard_handle_action(
                    guild,
                    user,
                    member,
                    action,
                    form_data,
                )
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("SuggestionBox dashboard action failed.")
                notifications.append(
                    {
                        "message": f"SuggestionBox dashboard action failed: {error}",
                        "category": "error",
                    }
                )
            else:
                notifications.extend(messages)

        source = await self._dashboard_source(guild, kwargs)
        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {
                "source": source,
                "expanded": True,
            },
        }

    async def _dashboard_member_can_manage(
        self,
        user: discord.User,
        guild: discord.Guild,
    ) -> typing.Tuple[typing.Optional[discord.Member], bool]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = (
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild)
        )
        return member, can_manage

    def _dashboard_form_data(self, kwargs: typing.Dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    def _dash_value(
        self,
        form_data: typing.Any,
        key: str,
        default: str = "",
    ) -> str:
        if hasattr(form_data, "get"):
            value = form_data.get(key, default)
        else:
            return default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        if value is None:
            return default
        return str(value)

    def _dash_bool(self, form_data: typing.Any, key: str) -> bool:
        if hasattr(form_data, "__contains__") and key in form_data:
            value = self._dash_value(form_data, key, "1").lower()
            return value not in {"0", "false", "off", "no", ""}
        return False

    def _dash_int(
        self,
        form_data: typing.Any,
        key: str,
        *,
        default: typing.Optional[int] = None,
        minimum: typing.Optional[int] = None,
        maximum: typing.Optional[int] = None,
        optional: bool = False,
    ) -> typing.Optional[int]:
        value = self._dash_value(form_data, key).strip()
        if optional and value == "":
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            if default is not None:
                number = default
            else:
                raise commands.BadArgument(f"`{key}` must be a whole number.")
        if minimum is not None:
            number = max(minimum, number)
        if maximum is not None:
            number = min(maximum, number)
        return number

    def _dash_optional_id(self, form_data: typing.Any, key: str) -> typing.Optional[int]:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(f"`{key}` must be a Discord ID.") from exc

    def _dash_csrf(self, kwargs: typing.Dict[str, typing.Any]) -> str:
        csrf_token = kwargs.get("csrf_token")
        if not isinstance(csrf_token, (tuple, list)) or len(csrf_token) != 2:
            return ""
        return (
            '<input type="hidden" name="csrf_token" value="'
            f'{html.escape(str(csrf_token[1]), quote=True)}">'
        )

    async def _dashboard_handle_action(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: typing.Optional[discord.Member],
        action: str,
        form_data: typing.Any,
    ) -> typing.List[typing.Dict[str, str]]:
        messages: typing.List[typing.Dict[str, str]] = []

        if action == "save_settings":
            await self._dashboard_save_settings(guild, form_data)
            messages.append({"message": "SuggestionBox settings saved.", "category": "success"})

        elif action == "submit_suggestion":
            record, message = await self._dashboard_submit_suggestion(guild, user, form_data)
            messages.append(
                {
                    "message": f"Suggestion #{record['id']} submitted: {message.jump_url}",
                    "category": "success",
                }
            )

        elif action == "set_status":
            suggestion_id, status = await self._dashboard_set_status(
                guild,
                user,
                member,
                form_data,
            )
            messages.append(
                {
                    "message": f"Suggestion #{suggestion_id} marked as {self._status_label(status)}.",
                    "category": "success",
                }
            )

        elif action == "add_comment":
            suggestion_id = await self._dashboard_add_comment(guild, user, form_data)
            messages.append(
                {
                    "message": f"Added a staff note to suggestion #{suggestion_id}.",
                    "category": "success",
                }
            )

        elif action == "create_thread":
            suggestion_id, thread = await self._dashboard_create_thread(guild, form_data)
            messages.append(
                {
                    "message": f"Created a discussion thread for suggestion #{suggestion_id}: {thread.mention}",
                    "category": "success",
                }
            )

        elif action == "delete_suggestion":
            suggestion_id = await self._dashboard_delete_suggestion(guild, user, form_data)
            messages.append(
                {
                    "message": f"Suggestion #{suggestion_id} deleted.",
                    "category": "success",
                }
            )

        elif action == "refresh_messages":
            count = await self._dashboard_refresh_messages(guild)
            messages.append(
                {
                    "message": f"Refreshed {count} tracked suggestion message(s).",
                    "category": "success",
                }
            )

        elif action == "reset_records":
            await self._dashboard_reset_records(guild, form_data)
            messages.append(
                {
                    "message": "SuggestionBox records have been reset.",
                    "category": "success",
                }
            )

        elif action:
            raise commands.BadArgument("Unknown SuggestionBox dashboard action.")

        return messages

    async def _dashboard_save_settings(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> None:
        suggestion_channel_id = self._dash_optional_id(form_data, "suggestion_channel_id")
        suggestion_channel = guild.get_channel(suggestion_channel_id) if suggestion_channel_id else None
        if suggestion_channel_id and not isinstance(suggestion_channel, discord.TextChannel):
            raise commands.BadArgument("Suggestion channel must be a text channel.")
        if self._dash_bool(form_data, "enabled") and suggestion_channel is None:
            raise commands.BadArgument("Choose a suggestion channel before enabling SuggestionBox.")

        review_channel_id = self._dash_optional_id(form_data, "review_channel_id")
        review_channel = guild.get_channel(review_channel_id) if review_channel_id else None
        if review_channel_id and not isinstance(review_channel, discord.TextChannel):
            raise commands.BadArgument("Review channel must be a text channel.")

        archive_minutes = self._dash_int(
            form_data,
            "thread_auto_archive_duration",
            default=1440,
        )
        if archive_minutes not in {60, 1440, 4320, 10080}:
            raise commands.BadArgument("Thread archive duration must be 60, 1440, 4320, or 10080.")

        color_value = self._dashboard_parse_color(self._dash_value(form_data, "embed_color"))
        next_id = self._dash_int(form_data, "next_id", default=1, minimum=1)

        guild_conf = self.config.guild(guild)
        await guild_conf.enabled.set(self._dash_bool(form_data, "enabled"))
        await guild_conf.suggestion_channel_id.set(suggestion_channel.id if suggestion_channel else None)
        await guild_conf.review_channel_id.set(review_channel.id if review_channel else None)
        await guild_conf.anonymous.set(self._dash_bool(form_data, "anonymous"))
        await guild_conf.allow_downvotes.set(self._dash_bool(form_data, "allow_downvotes"))
        await guild_conf.allow_self_vote.set(self._dash_bool(form_data, "allow_self_vote"))
        await guild_conf.create_threads.set(self._dash_bool(form_data, "create_threads"))
        await guild_conf.thread_auto_archive_duration.set(archive_minutes)
        await guild_conf.embed_color.set(color_value)
        await guild_conf.next_id.set(next_id)

    async def _dashboard_submit_suggestion(
        self,
        guild: discord.Guild,
        user: discord.User,
        form_data: typing.Any,
    ) -> typing.Tuple[typing.Dict[str, typing.Any], discord.Message]:
        text = self._dash_value(form_data, "suggestion_text").strip()
        if not text:
            raise commands.BadArgument("Suggestion text cannot be empty.")
        author_id = self._dash_optional_id(form_data, "suggestion_author_id")
        author = guild.get_member(author_id) if author_id else guild.get_member(user.id)
        if author is None:
            author = user
        return await self._submit_suggestion(guild, author, text)

    async def _dashboard_set_status(
        self,
        guild: discord.Guild,
        user: discord.User,
        member: typing.Optional[discord.Member],
        form_data: typing.Any,
    ) -> typing.Tuple[int, str]:
        suggestion_id = self._dash_int(form_data, "status_suggestion_id", minimum=1)
        status = self._normalise_status(self._dash_value(form_data, "suggestion_status", "open"))
        reason_text = self._dash_value(form_data, "status_reason").strip()
        reason = self._clean_text(reason_text, self.MAX_REASON_LENGTH) if reason_text else None
        actor = member or user

        async with self._guild_lock(guild.id):
            async with self.config.guild(guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.get(key)
                if not record:
                    raise commands.BadArgument(f"No suggestion with ID `{suggestion_id}` was found.")
                record["status"] = status
                record["updated_at"] = self._now_ts()
                record["decision_by"] = user.id
                record["decision_reason"] = reason
                record["decision_at"] = self._now_ts()
                suggestions[key] = record

        settings = await self.config.guild(guild).all()
        await self._sync_suggestion_message(guild, record, settings)
        await self._send_review_log(guild, record, self._status_label(status), actor, reason)
        notice = f"Suggestion #{suggestion_id} was marked as {self._status_label(status)}."
        if reason:
            notice += f"\nReason: {reason}"
        await self._send_thread_notice(guild, record, notice)
        return suggestion_id, status

    async def _dashboard_add_comment(
        self,
        guild: discord.Guild,
        user: discord.User,
        form_data: typing.Any,
    ) -> int:
        suggestion_id = self._dash_int(form_data, "comment_suggestion_id", minimum=1)
        comment = self._clean_text(
            self._dash_value(form_data, "staff_comment"),
            self.MAX_COMMENT_LENGTH,
        )

        async with self._guild_lock(guild.id):
            async with self.config.guild(guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.get(key)
                if not record:
                    raise commands.BadArgument(f"No suggestion with ID `{suggestion_id}` was found.")
                record.setdefault("staff_notes", []).append(
                    {
                        "staff_id": user.id,
                        "comment": comment,
                        "created_at": self._now_ts(),
                    }
                )
                record["updated_at"] = self._now_ts()
                suggestions[key] = record

        settings = await self.config.guild(guild).all()
        await self._sync_suggestion_message(guild, record, settings)
        await self._send_review_log(guild, record, "Commented", user, comment)
        await self._send_thread_notice(
            guild,
            record,
            f"Staff note added to suggestion #{suggestion_id}: {comment}",
        )
        return suggestion_id

    async def _dashboard_create_thread(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> typing.Tuple[int, discord.Thread]:
        suggestion_id = self._dash_int(form_data, "thread_suggestion_id", minimum=1)
        async with self._guild_lock(guild.id):
            settings = await self.config.guild(guild).all()
            suggestions = settings.get("suggestions") or {}
            key = self._suggestion_key(suggestion_id)
            record = suggestions.get(key)
            if not record:
                raise commands.BadArgument(f"No suggestion with ID `{suggestion_id}` was found.")
            if record.get("thread_id"):
                raise commands.BadArgument(f"Suggestion #{suggestion_id} already has a thread.")

            message = await self._fetch_suggestion_message(guild, record)
            if message is None:
                raise commands.BadArgument("I could not find the suggestion message.")

            thread = await self._create_suggestion_thread(
                guild,
                message,
                record,
                settings,
                raise_on_error=True,
            )
            if thread is None:
                raise commands.CommandError("I could not create a thread for that suggestion.")

            record["thread_id"] = thread.id
            record["updated_at"] = self._now_ts()
            async with self.config.guild(guild).suggestions() as stored_suggestions:
                stored_suggestions[key] = record

        await self._sync_suggestion_message(guild, record, settings)
        return suggestion_id, thread

    async def _dashboard_delete_suggestion(
        self,
        guild: discord.Guild,
        user: discord.User,
        form_data: typing.Any,
    ) -> int:
        suggestion_id = self._dash_int(form_data, "delete_suggestion_id", minimum=1)
        reason_text = self._dash_value(form_data, "delete_reason").strip()
        reason = self._clean_text(reason_text, self.MAX_REASON_LENGTH) if reason_text else None
        async with self._guild_lock(guild.id):
            async with self.config.guild(guild).suggestions() as suggestions:
                key = self._suggestion_key(suggestion_id)
                record = suggestions.pop(key, None)
                if not record:
                    raise commands.BadArgument(f"No suggestion with ID `{suggestion_id}` was found.")

        message = await self._fetch_suggestion_message(guild, record)
        if message is not None:
            with contextlib.suppress(discord.HTTPException):
                await message.delete()
        await self._send_review_log(guild, record, "Deleted", user, reason)
        return suggestion_id

    async def _dashboard_refresh_messages(self, guild: discord.Guild) -> int:
        settings = await self.config.guild(guild).all()
        suggestions = settings.get("suggestions") or {}
        count = 0
        for record in suggestions.values():
            await self._sync_suggestion_message(guild, record, settings)
            count += 1
        return count

    async def _dashboard_reset_records(self, guild: discord.Guild, form_data: typing.Any) -> None:
        if self._dash_value(form_data, "reset_confirmation").strip().lower() != "confirm":
            raise commands.BadArgument("Type `confirm` before resetting suggestion records.")
        await self.config.guild(guild).suggestions.set({})
        await self.config.guild(guild).next_id.set(1)

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: typing.Dict[str, typing.Any],
    ) -> str:
        settings = await self.config.guild(guild).all()
        suggestions = settings.get("suggestions") or {}
        csrf = self._dash_csrf(kwargs)

        counts = {status: 0 for status in self.VALID_STATUSES}
        for record in suggestions.values():
            status = str(record.get("status") or "open")
            counts[status] = counts.get(status, 0) + 1
        top_record = max(
            suggestions.values(),
            key=lambda record: self._score(record),
            default=None,
        )

        return f"""
        <style>
            .sb-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .sb-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .sb-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px; }}
            .sb-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
            .sb-card h2, .sb-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .sb-muted {{ color: #9ca3af; }}
            .sb-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .sb-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .sb-field input, .sb-field select, .sb-field textarea {{
                width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .sb-field textarea {{ min-height: 82px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
            .sb-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .sb-check input {{ width: auto; }}
            .sb-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; font-weight: 700; }}
            .sb-btn.secondary {{ background: #4b5563; }}
            .sb-btn.danger {{ background: #dc2626; }}
            .sb-nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 16px; }}
            .sb-nav a {{ color: #bfdbfe; border: 1px solid #374151; border-radius: 6px; padding: 6px 10px; text-decoration: none; }}
            .sb-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .sb-table th, .sb-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; vertical-align: top; }}
            .sb-table th {{ color: #d1d5db; }}
            .sb-inline {{ display: inline; }}
        </style>
        <div class="sb-wrap">
            <div class="sb-card">
                <h2>SuggestionBox Dashboard</h2>
                <div class="sb-nav">
                    <a href="#settings">Settings</a>
                    <a href="#suggestions">Suggestions</a>
                    <a href="#actions">Actions</a>
                    <a href="#maintenance">Maintenance</a>
                </div>
                <div class="sb-grid">
                    <div><div class="sb-muted">Total Suggestions</div><div class="sb-stat">{len(suggestions)}</div></div>
                    <div><div class="sb-muted">Open</div><div class="sb-stat">{counts.get("open", 0)}</div></div>
                    <div><div class="sb-muted">Approved</div><div class="sb-stat">{counts.get("approved", 0)}</div></div>
                    <div><div class="sb-muted">Implemented</div><div class="sb-stat">{counts.get("implemented", 0)}</div></div>
                    <div><div class="sb-muted">Top Score</div><div class="sb-stat">{self._score(top_record) if top_record else 0}</div></div>
                </div>
            </div>
            {self._dashboard_settings_section(guild, settings, csrf)}
            {self._dashboard_suggestions_section(guild, suggestions)}
            {self._dashboard_actions_section(suggestions, csrf)}
            {self._dashboard_maintenance_section(csrf)}
        </div>
        """

    def _dashboard_settings_section(
        self,
        guild: discord.Guild,
        settings: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        return f"""
        <div id="settings" class="sb-card">
            <h3>Settings</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_settings">
                <div class="sb-grid">
                    <div>
                        <label class="sb-check"><input type="checkbox" name="enabled" value="1" {self._checked(settings.get("enabled"))}> Enabled</label>
                        <label class="sb-check"><input type="checkbox" name="anonymous" value="1" {self._checked(settings.get("anonymous"))}> Anonymous Public Authors</label>
                        <label class="sb-check"><input type="checkbox" name="allow_downvotes" value="1" {self._checked(settings.get("allow_downvotes"))}> Allow Downvotes</label>
                        <label class="sb-check"><input type="checkbox" name="allow_self_vote" value="1" {self._checked(settings.get("allow_self_vote"))}> Allow Self Voting</label>
                        <label class="sb-check"><input type="checkbox" name="create_threads" value="1" {self._checked(settings.get("create_threads"))}> Create Discussion Threads</label>
                    </div>
                    <div class="sb-row">
                        {self._channel_select(guild, "suggestion_channel_id", "Suggestion Channel", settings.get("suggestion_channel_id"), include_none=False)}
                        {self._channel_select(guild, "review_channel_id", "Review Log Channel", settings.get("review_channel_id"))}
                        {self._input("embed_color", "Open Embed Color", self._color_hex(settings.get("embed_color")))}
                        {self._input("next_id", "Next Suggestion ID", settings.get("next_id") or 1, "number", min_value=1)}
                        <div class="sb-field"><label>Thread Auto-Archive</label><select name="thread_auto_archive_duration">
                            {self._option(60, "1 hour", settings.get("thread_auto_archive_duration"))}
                            {self._option(1440, "1 day", settings.get("thread_auto_archive_duration"))}
                            {self._option(4320, "3 days", settings.get("thread_auto_archive_duration"))}
                            {self._option(10080, "7 days", settings.get("thread_auto_archive_duration"))}
                        </select></div>
                    </div>
                </div>
                <button class="sb-btn" type="submit">Save Settings</button>
            </form>
        </div>
        """

    def _dashboard_suggestions_section(
        self,
        guild: discord.Guild,
        suggestions: typing.Dict[str, typing.Any],
    ) -> str:
        rows = []
        records = sorted(
            suggestions.values(),
            key=lambda record: int(record.get("id") or 0),
            reverse=True,
        )
        for record in records[:100]:
            author_id = record.get("author_id")
            author = guild.get_member(int(author_id)) if author_id else None
            rows.append(
                "<tr>"
                f"<td>{self._h(record.get('id'))}</td>"
                f"<td>{self._h(self._status_label(str(record.get('status') or 'open')))}</td>"
                f"<td>{self._h(author or author_id or 'Unknown')}</td>"
                f"<td>{self._score(record)}</td>"
                f"<td>{len(record.get('upvotes', []))}</td>"
                f"<td>{len(record.get('downvotes', []))}</td>"
                f"<td>{self._h(self._short_text(record.get('text'), 140))}</td>"
                "</tr>"
            )
        table = "".join(rows) or (
            '<tr><td colspan="7" class="sb-muted">No suggestions have been stored.</td></tr>'
        )
        return f"""
        <div id="suggestions" class="sb-card">
            <h3>Recent Suggestions</h3>
            <table class="sb-table">
                <thead><tr><th>ID</th><th>Status</th><th>Author</th><th>Score</th><th>Up</th><th>Down</th><th>Suggestion</th></tr></thead>
                <tbody>{table}</tbody>
            </table>
        </div>
        """

    def _dashboard_actions_section(
        self,
        suggestions: typing.Dict[str, typing.Any],
        csrf: str,
    ) -> str:
        options = self._suggestion_options(suggestions)
        status_options = "".join(
            self._option(status, label, "approved")
            for status, label in self.STATUS_LABELS.items()
        )
        return f"""
        <div id="actions" class="sb-card">
            <h3>Actions</h3>
            <div class="sb-grid">
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="submit_suggestion">
                    {self._textarea("suggestion_text", "Submit Suggestion", "", rows=4)}
                    {self._input("suggestion_author_id", "Author Member ID", "")}
                    <button class="sb-btn" type="submit">Submit Suggestion</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="set_status">
                    <div class="sb-row">
                        <div class="sb-field"><label>Suggestion</label><select name="status_suggestion_id">{options}</select></div>
                        <div class="sb-field"><label>Status</label><select name="suggestion_status">{status_options}</select></div>
                    </div>
                    {self._textarea("status_reason", "Reason", "", rows=3)}
                    <button class="sb-btn" type="submit">Set Status</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="add_comment">
                    <div class="sb-field"><label>Suggestion</label><select name="comment_suggestion_id">{options}</select></div>
                    {self._textarea("staff_comment", "Staff Comment", "", rows=3)}
                    <button class="sb-btn secondary" type="submit">Add Comment</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="create_thread">
                    <div class="sb-field"><label>Suggestion</label><select name="thread_suggestion_id">{options}</select></div>
                    <button class="sb-btn secondary" type="submit">Create Thread</button>
                </form>
                <form method="POST">
                    {csrf}
                    <input type="hidden" name="action" value="delete_suggestion">
                    <div class="sb-field"><label>Suggestion</label><select name="delete_suggestion_id">{options}</select></div>
                    {self._textarea("delete_reason", "Reason", "", rows=3)}
                    <button class="sb-btn danger" type="submit">Delete Suggestion</button>
                </form>
            </div>
        </div>
        """

    def _dashboard_maintenance_section(self, csrf: str) -> str:
        return f"""
        <div id="maintenance" class="sb-card">
            <h3>Maintenance</h3>
            <form class="sb-inline" method="POST">
                {csrf}
                <input type="hidden" name="action" value="refresh_messages">
                <button class="sb-btn secondary" type="submit">Refresh Tracked Messages</button>
            </form>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="reset_records">
                <div class="sb-row">
                    {self._input("reset_confirmation", "Type confirm to reset records", "")}
                </div>
                <button class="sb-btn danger" type="submit">Reset Suggestion Records</button>
            </form>
        </div>
        """

    def _suggestion_options(self, suggestions: typing.Dict[str, typing.Any]) -> str:
        if not suggestions:
            return '<option value="">No suggestions stored</option>'
        rows = []
        for record in sorted(
            suggestions.values(),
            key=lambda item: int(item.get("id") or 0),
            reverse=True,
        )[:100]:
            label = f"#{record.get('id')} - {self._short_text(record.get('text'), 80)}"
            rows.append(f'<option value="{self._h(record.get("id"))}">{self._h(label)}</option>')
        return "".join(rows)

    def _channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
        *,
        include_none: bool = True,
    ) -> str:
        options = ['<option value="">None</option>'] if include_none else []
        for channel in sorted(guild.text_channels, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{channel.id}" {self._selected(channel.id, selected)}>#{self._h(channel.name)}</option>'
            )
        return (
            f'<div class="sb-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(options)}</select></div>'
        )

    def _dashboard_parse_color(self, value: str) -> int:
        value = value.strip()
        if not value:
            return self.DEFAULT_COLOR
        try:
            return discord.Color.from_str(value).value
        except ValueError as exc:
            raise commands.BadArgument("Use a valid Discord color, such as `#5865F2`.") from exc

    def _color_hex(self, value: typing.Any) -> str:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = self.DEFAULT_COLOR
        return f"#{number:06X}"

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
        *,
        min_value: typing.Optional[int] = None,
        max_value: typing.Optional[int] = None,
    ) -> str:
        attrs = []
        if min_value is not None:
            attrs.append(f'min="{min_value}"')
        if max_value is not None:
            attrs.append(f'max="{max_value}"')
        return (
            f'<div class="sb-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _textarea(self, name: str, label: str, value: typing.Any, *, rows: int = 4) -> str:
        return (
            f'<div class="sb-field"><label>{self._h(label)}</label>'
            f'<textarea name="{self._h(name)}" rows="{rows}">{self._h(value)}</textarea></div>'
        )

    def _option(self, value: typing.Any, label: str, selected: typing.Any) -> str:
        return f'<option value="{self._h(value)}" {self._selected(value, selected)}>{self._h(label)}</option>'

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _checked(self, value: typing.Any) -> str:
        return "checked" if bool(value) else ""

    def _short_text(self, value: typing.Any, limit: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)] + "..."

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
