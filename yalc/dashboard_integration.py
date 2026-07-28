# ruff: noqa: E501
"""Fully standalone Red-Web-Dashboard control center for YALC."""

from __future__ import annotations

import datetime
import html
import logging
import re
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.yalc.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """YALC event routing, privacy, audit, ignore, and journal controls."""

    def __init__(self, bot, *args, **kwargs) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Operate YALC's complete logging control center.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any) -> dict[str, Any]:
        if not await self._yd_can_manage(user, guild):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            form = self._yd_form(kwargs)
            try:
                message = await self._yd_action(user, guild, form)
            except (commands.CommandError, ValueError) as error:
                notices.append({"message": str(error), "category": "error"})
            except Exception:
                log.exception("YALC dashboard action failed for guild %s", guild.id)
                notices.append(
                    {"message": "The YALC dashboard action failed. Check the bot log for details.", "category": "error"},
                )
            else:
                notices.append({"message": message, "category": "success"})
        settings = await self.config.guild(guild).all()
        journal_stats = await self._yd_journal_stats(guild.id)
        source = self._yd_source(user, guild, settings, journal_stats, self._yd_csrf(kwargs))
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}

    async def _yd_action(self, user, guild, form) -> str:
        action = self._yd_value(form, "action")
        if action == "save_core":
            await self._yd_save_core(guild, form)
            return "Core logging, audit, delivery, and journal settings saved."
        if action == "save_events":
            await self._yd_save_events(guild, form)
            return "Event routes, toggles, and colors saved."
        if action == "enable_all_events":
            async with self.config.guild(guild).events() as events:
                for event_type in self.event_descriptions:
                    events[event_type] = True
            self._invalidate_settings_cache(guild)
            return f"Enabled all {len(self.event_descriptions)} YALC events."
        if action == "disable_all_events":
            async with self.config.guild(guild).events() as events:
                for event_type in self.event_descriptions:
                    events[event_type] = False
            self._invalidate_settings_cache(guild)
            return f"Disabled all {len(self.event_descriptions)} YALC events."
        if action == "smart_route_unset":
            suggestions = self._yd_smart_route_suggestions(guild)
            routed = []
            async with self.config.guild(guild).event_channels() as event_channels:
                for event_type, channel in suggestions.items():
                    if not event_channels.get(event_type):
                        event_channels[event_type] = channel.id
                        routed.append(event_type)
            self._invalidate_settings_cache(guild)
            if not routed:
                return "No unset event routes had a usable logging-channel suggestion."
            used_channels = {suggestions[event].id for event in routed}
            return f"Smart-routed {len(routed)} unset events across {len(used_channels)} existing log channels."
        if action == "save_filters":
            await self._yd_save_filters(guild, form)
            return "Ignore and proxy filters saved."
        if action == "add_rule":
            await self._yd_add_rule(user, guild, form)
            return "Granular ignore rule added."
        if action == "delete_rule":
            await self._yd_delete_rule(guild, form)
            return "Granular ignore rule removed."
        if action == "test_event":
            return await self._yd_test_event(guild, form)
        if action == "prune_journal":
            if self._journal is None:
                raise commands.BadArgument("The event journal is unavailable.")
            retention = await self.config.guild(guild).log_retention_days()
            deleted = await self._journal.prune(guild.id, int(retention))
            return f"Pruned {deleted:,} expired journal events."
        if action == "clear_journal":
            if self._yd_value(form, "journal_confirmation") != "CONFIRM":
                raise commands.BadArgument("Type CONFIRM to permanently clear the journal.")
            if self._journal is None:
                raise commands.BadArgument("The event journal is unavailable.")
            deleted = await self._journal.clear_guild(guild.id)
            return f"Permanently cleared {deleted:,} journal events."
        raise commands.BadArgument("Choose a valid dashboard action.")

    async def _yd_save_core(self, guild, form) -> None:
        fallback_id = self._yd_channel_id(guild, form, "fallback_channel_id", optional=True)
        retention = self._yd_int(form, "log_retention_days", 1, 3650)
        command_mode = self._yd_value(form, "command_log_mode", "all")
        if command_mode not in {"all", "staff", "none"}:
            raise commands.BadArgument("Choose a valid command logging mode.")
        conf = self.config.guild(guild)
        values = {
            "include_thumbnails": self._yd_checked(form, "include_thumbnails"),
            "ignore_bots": self._yd_checked(form, "ignore_bots"),
            "ignore_webhooks": self._yd_checked(form, "ignore_webhooks"),
            "ignore_tupperbox": self._yd_checked(form, "ignore_tupperbox"),
            "ignore_apps": self._yd_checked(form, "ignore_apps"),
            "detect_proxy_deletes": self._yd_checked(form, "detect_proxy_deletes"),
            "raw_message_events": self._yd_checked(form, "raw_message_events"),
            "audit_only_events": self._yd_checked(form, "audit_only_events"),
            "fallback_channel_id": fallback_id,
            "journal_enabled": self._yd_checked(form, "journal_enabled"),
            "journal_include_message_content": self._yd_checked(form, "journal_include_message_content"),
            "log_retention_days": retention,
            "command_log_mode": command_mode,
        }
        for key, value in values.items():
            await getattr(conf, key).set(value)
        self._invalidate_settings_cache(guild)

    async def _yd_save_events(self, guild, form) -> None:
        events = {}
        channels = {}
        colors = {}
        for event in self.event_descriptions:
            events[event] = self._yd_checked(form, f"event__{event}")
            channels[event] = self._yd_channel_id(guild, form, f"channel__{event}", optional=True)
            raw_color = self._yd_value(form, f"color__{event}").strip().lstrip("#")
            if raw_color:
                try:
                    color = int(raw_color, 16)
                except ValueError as error:
                    raise commands.BadArgument(f"Invalid color for {event}.") from error
                if not 0 <= color <= 0xFFFFFF:
                    raise commands.BadArgument(f"Invalid color for {event}.")
                colors[event] = color
        conf = self.config.guild(guild)
        await conf.events.set(events)
        await conf.event_channels.set(channels)
        await conf.event_colors.set(colors)
        self._invalidate_settings_cache(guild)

    async def _yd_save_filters(self, guild, form) -> None:
        conf = self.config.guild(guild)
        await conf.ignored_users.set(self._yd_id_lines(form, "ignored_users", maximum=500))
        await conf.tupperbox_ids.set(self._yd_id_lines(form, "tupperbox_ids", maximum=50))
        await conf.ignored_roles.set(self._yd_selected_ids(guild, form, "ignored_roles", "role"))
        await conf.ignored_channels.set(self._yd_selected_ids(guild, form, "ignored_channels", "channel"))
        await conf.ignored_categories.set(self._yd_selected_ids(guild, form, "ignored_categories", "category"))
        await conf.message_prefix_filter.set(self._yd_text_lines(form, "message_prefix_filter", 50, 40))
        await conf.webhook_name_filter.set(self._yd_text_lines(form, "webhook_name_filter", 50, 80))
        self._invalidate_settings_cache(guild)

    async def _yd_add_rule(self, user, guild, form) -> None:
        event_type = self._yd_value(form, "rule_event")
        if event_type not in self.event_descriptions:
            raise commands.BadArgument("Choose a valid event for the ignore rule.")
        try:
            user_id = int(self._yd_value(form, "rule_user_id"))
        except ValueError as error:
            raise commands.BadArgument("Enter a valid Discord user ID.") from error
        if guild.get_member(user_id) is None:
            raise commands.BadArgument("That user is not currently in this server.")
        channel_id = self._yd_channel_id(guild, form, "rule_channel_id", optional=False)
        reason = self._yd_value(form, "rule_reason").strip()[:300] or None
        conf = self.config.guild(guild)
        async with conf.granular_ignores() as rules:
            if any(
                rule.get("event_type") == event_type and rule.get("user_id") == user_id and rule.get("channel_id") == channel_id
                for rule in rules
            ):
                raise commands.BadArgument("That granular ignore rule already exists.")
            rules.append(
                {
                    "event_type": event_type,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "created_by": user.id,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "reason": reason,
                },
            )
        self._invalidate_settings_cache(guild)

    async def _yd_delete_rule(self, guild, form) -> None:
        index = self._yd_int(form, "rule_index", 1, 100000) - 1
        conf = self.config.guild(guild)
        async with conf.granular_ignores() as rules:
            if index >= len(rules):
                raise commands.BadArgument("That ignore rule no longer exists.")
            rules.pop(index)
        self._invalidate_settings_cache(guild)

    async def _yd_test_event(self, guild, form) -> str:
        event_type = self._yd_value(form, "test_event_type")
        if event_type not in self.event_descriptions:
            raise commands.BadArgument("Choose a valid event to test.")
        channel = await self.get_log_channel(guild, event_type)
        if channel is None:
            raise commands.BadArgument("That event does not have a valid destination channel.")
        embed = self.create_embed(event_type, f"🧪 Test delivery for `{event_type}` from the YALC dashboard.")
        message = await self.safe_send(channel, embed=embed)
        if message is None:
            raise commands.CommandError("The test log could not be delivered.")
        return f"Test event delivered to #{channel.name}."

    async def _yd_journal_stats(self, guild_id: int) -> dict[str, Any]:
        if self._journal is None:
            return {"count": 0, "oldest": None, "newest": None}
        return await self._journal.stats(guild_id)

    def _yd_source(self, user, guild, settings, journal_stats, csrf) -> str:
        enabled_count = sum(bool(value) for value in settings.get("events", {}).values())
        routed_count = sum(bool(value) for value in settings.get("event_channels", {}).values())
        delivery_issues = 0
        for channel_id in settings.get("event_channels", {}).values():
            if not channel_id:
                continue
            route = guild.get_channel(channel_id)
            if route is None:
                delivery_issues += 1
                continue
            if guild.me is None:
                delivery_issues += 1
                continue
            permissions = route.permissions_for(guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                delivery_issues += 1
        audit_stats = self._audit_correlator.stats()
        bot_member = guild.me
        view_audit = bool(bot_member and bot_member.guild_permissions.view_audit_log)
        moderation_intent = bool(getattr(self.bot.intents, "moderation", getattr(self.bot.intents, "guild_moderation", False)))
        health = "Healthy" if view_audit and moderation_intent else "Needs attention"
        health_class = "ok" if health == "Healthy" else "warn"
        core = self._yd_core_form(guild, settings, csrf)
        route_suggestions = self._yd_smart_route_suggestions(guild)
        events = self._yd_event_form(guild, settings, csrf, route_suggestions)
        filters = self._yd_filter_form(guild, settings, csrf)
        rules = self._yd_rules(guild, settings, csrf)
        journal_count = int(journal_stats.get("count") or 0)
        return f"""
<section class="yd"><style>
.yd{{color:#f2f3f5!important;color-scheme:dark}}
.yd h2,.yd h3,.yd h4,.yd p,.yd label,.yd th,.yd td,.yd small{{color:#f2f3f5!important}}
.yd .card{{background:#2b2d31!important;color:#f2f3f5!important;border:1px solid #4e5058!important;border-radius:.75rem;padding:1rem;margin-bottom:1rem;box-shadow:none!important}}
.yd .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem}}
.yd .stat strong{{display:block;font-size:1.5rem}}
.yd .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:1rem}}
.yd label{{display:flex!important;flex-direction:column;gap:.4rem;font-weight:600;line-height:1.35}}
.yd .check{{flex-direction:row!important;align-items:center;min-height:2rem}}
.yd input:not([type="checkbox"]):not([type="color"]),.yd select,.yd textarea{{box-sizing:border-box;width:100%;padding:.65rem .75rem;border:1px solid #4e5058!important;border-radius:.4rem;background:#1e1f22!important;color:#f2f3f5!important;-webkit-text-fill-color:#f2f3f5!important}}
.yd input::placeholder,.yd textarea::placeholder{{color:#a7aab0!important;opacity:1}}
.yd input[type="checkbox"]{{width:1.15rem!important;height:1.15rem!important;min-width:1.15rem;accent-color:#5865f2}}
.yd input[type="color"]{{width:4.5rem!important;height:2.75rem!important;padding:.2rem!important;border:1px solid #4e5058!important;border-radius:.4rem;background:#1e1f22!important}}
.yd select{{min-height:2.75rem}}
.yd select option{{background:#1e1f22;color:#f2f3f5}}
.yd select[multiple],.yd textarea{{min-height:9rem}}
.yd .choices,.yd .choices__inner{{color:#f2f3f5!important}}
.yd .choices__inner{{box-sizing:border-box;min-height:2.75rem!important;background:#1e1f22!important;border:1px solid #4e5058!important;border-radius:.4rem!important}}
.yd .choices__input{{background:#1e1f22!important;color:#f2f3f5!important;border-color:#4e5058!important;-webkit-text-fill-color:#f2f3f5!important}}
.yd .choices__list--single,.yd .choices__list--multiple,.yd .choices__item{{color:#f2f3f5!important}}
.yd .choices__list--multiple .choices__item{{background:#5865f2!important;border-color:#7983f5!important}}
.yd .choices__list--dropdown,.yd .choices__list[aria-expanded]{{background:#1e1f22!important;color:#f2f3f5!important;border:1px solid #4e5058!important;z-index:50}}
.yd .choices__list--dropdown .choices__item--selectable.is-highlighted,.yd .choices__list[aria-expanded] .choices__item--selectable.is-highlighted{{background:#3f4147!important}}
.yd .choices__placeholder{{color:#a7aab0!important;opacity:1!important}}
.yd .choices[data-type*="select-one"]::after{{border-color:#f2f3f5 transparent transparent!important}}
.yd .select2-container .select2-selection,.yd .select2-dropdown{{background:#1e1f22!important;color:#f2f3f5!important;border-color:#4e5058!important}}
.yd .select2-container .select2-selection__rendered,.yd .select2-results__option{{color:#f2f3f5!important}}
.yd table{{width:100%;border-collapse:collapse;color:#f2f3f5!important}}
.yd th,.yd td{{padding:.65rem;border-bottom:1px solid #4e5058;text-align:left;vertical-align:middle;background:#2b2d31!important}}
.yd code{{color:#c9cdfb!important;background:#1e1f22;padding:.12rem .3rem;border-radius:.25rem}}
.yd .events{{max-height:48rem;overflow:auto;border:1px solid #4e5058;border-radius:.5rem}}
.yd .ok{{color:#57f287!important}}.yd .warn{{color:#fee75c!important}}
.yd .actions{{display:flex;gap:.5rem;flex-wrap:wrap;align-items:end}}
.yd .bulk-actions{{margin-bottom:.75rem}}
.yd .suggestion{{display:inline-block;margin-top:.3rem;color:#57f287!important}}
.yd small{{opacity:.82;font-weight:400}}
.yd hr{{border-color:#4e5058}}
</style><h2>YALC Logging Control Center</h2><p>Configure delivery, audit attribution, privacy, filtering, and searchable history for <strong>{html.escape(guild.name)}</strong>.</p>
<div class="stats"><div class="card stat"><strong>{enabled_count}/{len(self.event_descriptions)}</strong>events enabled</div><div class="card stat"><strong>{routed_count}</strong>event routes</div><div class="card stat"><strong class="{"ok" if delivery_issues == 0 else "warn"}">{delivery_issues}</strong>delivery issues</div><div class="card stat"><strong>{journal_count:,}</strong>journal records</div><div class="card stat"><strong class="{health_class}">{health}</strong>audit stream</div><div class="card stat"><strong>{audit_stats["matches"]}</strong>audit matches</div><div class="card stat"><strong>{audit_stats["misses"]}</strong>audit misses</div></div>
<div class="card"><h3>Audit readiness</h3><p>View Audit Log: <strong class="{"ok" if view_audit else "warn"}">{"Yes" if view_audit else "Missing"}</strong> · Guild Moderation intent: <strong class="{"ok" if moderation_intent else "warn"}">{"Enabled" if moderation_intent else "Disabled"}</strong> · Cached audit entries: {audit_stats["cached_entries"]} · Deduplicated: {audit_stats["duplicates"]}</p></div>
{core}{events}{filters}{rules}</section>"""

    def _yd_core_form(self, guild, settings, csrf):
        fallback = self._yd_channel_options(guild, settings.get("fallback_channel_id"), "No fallback — fail closed")

        def check(key, default=False):
            return " checked" if settings.get(key, default) else ""

        mode = settings.get("command_log_mode", "all")

        def selected(value):
            return " selected" if mode == value else ""

        return f"""<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save_core"><h3>Core behavior & privacy</h3><div class="grid"><label class="check"><input type="checkbox" name="include_thumbnails"{check("include_thumbnails", True)}> Include user thumbnails</label><label class="check"><input type="checkbox" name="raw_message_events"{check("raw_message_events", True)}> Log uncached message events</label><label class="check"><input type="checkbox" name="audit_only_events"{check("audit_only_events", True)}> Log audit-only events</label><label class="check"><input type="checkbox" name="ignore_bots"{check("ignore_bots")}> Ignore bots</label><label class="check"><input type="checkbox" name="ignore_webhooks"{check("ignore_webhooks")}> Ignore webhooks</label><label class="check"><input type="checkbox" name="ignore_tupperbox"{check("ignore_tupperbox", True)}> Ignore known/configured proxy messages</label><label class="check"><input type="checkbox" name="ignore_apps"{check("ignore_apps", True)}> Ignore application messages</label><label class="check"><input type="checkbox" name="detect_proxy_deletes"{check("detect_proxy_deletes", True)}> Suppress likely proxy source-message deletes</label><label>Explicit fallback channel<select name="fallback_channel_id">{fallback}</select><small>YALC never falls back to an arbitrary public channel.</small></label><label>Command logging<select name="command_log_mode"><option value="all"{selected("all")}>All commands</option><option value="staff"{selected("staff")}>Staff commands only</option><option value="none"{selected("none")}>Disabled by policy</option></select></label></div><h4>Optional local journal</h4><div class="grid"><label class="check"><input type="checkbox" name="journal_enabled"{check("journal_enabled")}> Store searchable event metadata</label><label class="check"><input type="checkbox" name="journal_include_message_content"{check("journal_include_message_content")}> Include message content in journal</label><label>Retention days<input type="number" name="log_retention_days" min="1" max="3650" value="{int(settings.get("log_retention_days", 7))}"></label></div><button class="btn btn-primary">Save Core Settings</button></form>"""

    def _yd_event_form(self, guild, settings, csrf, suggestions):
        rows = []
        channels = settings.get("event_channels", {})
        enabled = settings.get("events", {})
        colors = settings.get("event_colors", {})
        for event, (emoji, description) in self.event_descriptions.items():
            route = self._yd_channel_options(guild, channels.get(event), "Not routed")
            color = int(colors.get(event, self._get_event_color(event)))
            suggestion = suggestions.get(event) if not channels.get(event) else None
            suggestion_note = (
                f'<br><small class="suggestion">Suggested: #{html.escape(suggestion.name)}</small>'
                if suggestion is not None
                else ""
            )
            rows.append(
                f'<tr><td><label class="check"><input type="checkbox" name="event__{event}"{" checked" if enabled.get(event) else ""}> {emoji} <code>{event}</code><br><small>{html.escape(description)}</small></label></td><td><select name="channel__{event}">{route}</select>{suggestion_note}</td><td><input type="color" name="color__{event}" value="#{color:06x}" aria-label="{event} color"></td></tr>',
            )
        event_options = "".join(
            f'<option value="{event}">{html.escape(description)}</option>'
            for event, (_emoji, description) in self.event_descriptions.items()
        )
        unset_count = sum(not channels.get(event) for event in self.event_descriptions)
        suggested_count = sum(event in suggestions and not channels.get(event) for event in self.event_descriptions)
        return f"""<div class="card"><h3>Event routing & presentation</h3><p><strong>{unset_count}</strong> routes are unset; YALC found sensible existing log-channel suggestions for <strong>{suggested_count}</strong> of them. Smart routing never overwrites a route you already chose.</p><div class="actions bulk-actions"><form method="POST">{csrf}<input type="hidden" name="action" value="enable_all_events"><button class="btn btn-success">Enable All Events</button></form><form method="POST">{csrf}<input type="hidden" name="action" value="disable_all_events"><button class="btn btn-danger">Disable All Events</button></form><form method="POST">{csrf}<input type="hidden" name="action" value="smart_route_unset"><button class="btn btn-secondary">Smart Route Unset Events</button></form></div><hr><form method="POST">{csrf}<input type="hidden" name="action" value="save_events"><div class="events"><table><thead><tr><th>Event</th><th>Destination</th><th>Color</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><button class="btn btn-primary">Save Event Matrix</button></form><hr><form method="POST" class="actions">{csrf}<input type="hidden" name="action" value="test_event"><select name="test_event_type">{event_options}</select><button class="btn btn-secondary">Send Test Event</button></form></div>"""

    def _yd_filter_form(self, guild, settings, csrf):
        role_options = self._yd_multi_options(
            (role for role in reversed(guild.roles) if not role.is_default()),
            settings.get("ignored_roles", []),
        )
        channel_options = self._yd_multi_options(guild.text_channels, settings.get("ignored_channels", []), prefix="#")
        category_options = self._yd_multi_options(guild.categories, settings.get("ignored_categories", []))
        users = html.escape("\n".join(str(item) for item in settings.get("ignored_users", [])))
        tupper = html.escape("\n".join(str(item) for item in settings.get("tupperbox_ids", [])))
        prefixes = html.escape("\n".join(settings.get("message_prefix_filter", [])))
        webhooks = html.escape("\n".join(settings.get("webhook_name_filter", [])))
        return f"""<form method="POST" class="card">{csrf}<input type="hidden" name="action" value="save_filters"><h3>Broad ignores & proxy filters</h3><div class="grid"><label>Proxy application/bot IDs<textarea name="tupperbox_ids" placeholder="One application or bot ID per line">{tupper}</textarea><small>Tupperbox and PluralKit are recognized automatically; add IDs for other proxy systems here.</small></label><label>Proxy command prefixes<textarea name="message_prefix_filter" placeholder="One prefix per line">{prefixes}</textarea></label><label>Webhook name filters<textarea name="webhook_name_filter" placeholder="One partial name per line">{webhooks}</textarea></label><label>Ignored user IDs<textarea name="ignored_users" placeholder="One user ID per line">{users}</textarea></label><label>Ignored roles<select name="ignored_roles" multiple>{role_options}</select></label><label>Ignored channels<select name="ignored_channels" multiple>{channel_options}</select></label><label>Ignored categories<select name="ignored_categories" multiple>{category_options}</select></label></div><button class="btn btn-primary">Save Filters</button></form>"""

    def _yd_rules(self, guild, settings, csrf):
        rules = settings.get("granular_ignores", [])
        rows = []
        for index, rule in enumerate(rules, start=1):
            member = guild.get_member(rule.get("user_id") or 0)
            channel = guild.get_channel(rule.get("channel_id") or 0)
            rows.append(
                f'<tr><td>{index}</td><td><code>{html.escape(str(rule.get("event_type", "unknown")))}</code></td><td>{html.escape(str(member or rule.get("user_id", "Unknown")))}</td><td>{"#" + html.escape(channel.name) if channel else rule.get("channel_id", "Unknown")}</td><td>{html.escape(str(rule.get("reason") or "—"))}</td><td><form method="POST">{csrf}<input type="hidden" name="action" value="delete_rule"><input type="hidden" name="rule_index" value="{index}"><button class="btn btn-sm btn-danger">Remove</button></form></td></tr>',
            )
        table_rows = "".join(rows) or '<tr><td colspan="6">No granular ignore rules.</td></tr>'
        event_options = "".join(
            f'<option value="{event}">{html.escape(description)}</option>'
            for event, (_emoji, description) in self.event_descriptions.items()
        )
        channels = self._yd_channel_options(guild, None, "Choose a channel…")
        return f"""<div class="card"><h3>Granular ignore rules</h3><div style="overflow:auto"><table><thead><tr><th>#</th><th>Event</th><th>User</th><th>Channel</th><th>Reason</th><th></th></tr></thead><tbody>{table_rows}</tbody></table></div><form method="POST">{csrf}<input type="hidden" name="action" value="add_rule"><div class="grid"><label>Event<select name="rule_event">{event_options}</select></label><label>User ID<input name="rule_user_id" inputmode="numeric" required></label><label>Channel<select name="rule_channel_id" required>{channels}</select></label><label>Reason<input name="rule_reason" maxlength="300"></label></div><button class="btn btn-secondary">Add Ignore Rule</button></form><hr><h3>Journal maintenance</h3><div class="actions"><form method="POST">{csrf}<input type="hidden" name="action" value="prune_journal"><button class="btn btn-secondary">Prune Journal Now</button></form><form method="POST">{csrf}<input type="hidden" name="action" value="clear_journal"><input name="journal_confirmation" placeholder="Type CONFIRM" required><button class="btn btn-danger">Clear Journal Permanently</button></form></div></div>"""

    async def _yd_can_manage(self, user, guild):
        member = guild.get_member(user.id)
        return bool(
            user.id in getattr(self.bot, "owner_ids", set())
            or user.id == guild.owner_id
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild),
        )

    @staticmethod
    def _yd_form(kwargs):
        data = kwargs.get("data") or {}
        return (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data

    @staticmethod
    def _yd_value(form, key, default=""):
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _yd_values(cls, form, key):
        if hasattr(form, "getlist"):
            return [str(value) for value in form.getlist(key)]
        value = form.get(key, []) if hasattr(form, "get") else []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
        return [str(value)] if value not in {None, ""} else []

    @classmethod
    def _yd_checked(cls, form, key):
        return cls._yd_value(form, key).lower() in {"1", "true", "on", "yes"}

    @classmethod
    def _yd_int(cls, form, key, minimum, maximum):
        try:
            value = int(cls._yd_value(form, key))
        except ValueError as error:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be a number.") from error
        if not minimum <= value <= maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} must be {minimum}–{maximum}.")
        return value

    @classmethod
    def _yd_channel_id(cls, guild, form, key, *, optional):
        raw = cls._yd_value(form, key).strip()
        if not raw and optional:
            return None
        try:
            channel = guild.get_channel(int(raw))
        except ValueError as error:
            raise commands.BadArgument("Choose a valid text channel.") from error
        if channel not in guild.text_channels:
            raise commands.BadArgument("Choose a valid text channel.")
        return channel.id

    @classmethod
    def _yd_id_lines(cls, form, key, *, maximum):
        values = []
        for line in cls._yd_value(form, key).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                values.append(int(line))
            except ValueError as error:
                raise commands.BadArgument(f"{key.replace('_', ' ')} contains an invalid Discord ID.") from error
        if len(values) > maximum:
            raise commands.BadArgument(f"{key.replace('_', ' ')} supports at most {maximum} IDs.")
        return list(dict.fromkeys(values))

    @classmethod
    def _yd_text_lines(cls, form, key, maximum, max_length):
        values = [line.strip() for line in cls._yd_value(form, key).splitlines() if line.strip()]
        if len(values) > maximum or any(len(value) > max_length for value in values):
            raise commands.BadArgument(f"{key.replace('_', ' ')} exceeds its entry or length limit.")
        return list(dict.fromkeys(values))

    @classmethod
    def _yd_selected_ids(cls, guild, form, key, kind):
        valid = {
            item.id
            for item in (guild.roles if kind == "role" else guild.categories if kind == "category" else guild.text_channels)
        }
        selected = []
        for raw in cls._yd_values(form, key):
            try:
                item_id = int(raw)
            except ValueError as error:
                raise commands.BadArgument(f"Choose valid {kind}s.") from error
            if item_id not in valid:
                raise commands.BadArgument(f"Choose valid {kind}s.")
            selected.append(item_id)
        return list(dict.fromkeys(selected))

    def _yd_smart_route_suggestions(self, guild):
        """Choose the best existing logging channel for each event without mutating config."""
        group_terms = {
            "application": {"application", "applications", "app", "apps", "bot", "command", "commands"},
            "channel": {"channel", "channels", "permission", "permissions", "overwrite", "overwrites"},
            "discord_automod": {"automod", "auto-mod", "safety"},
            "emoji": {"emoji", "emojis"},
            "event": {"event", "events", "scheduled"},
            "invite": {"invite", "invites"},
            "message": {"message", "messages", "chat"},
            "moderation": {"mod", "mods", "moderation", "audit", "staff"},
            "role": {"role", "roles"},
            "server": {"server", "guild"},
            "soundboard": {"sound", "sounds", "soundboard"},
            "stage": {"stage", "stages"},
            "sticker": {"sticker", "stickers"},
            "thread": {"thread", "threads", "forum", "forums"},
            "user": {"member", "members", "user", "users"},
            "voice": {"voice", "voices", "vc"},
            "webhook": {"webhook", "webhooks", "hook", "hooks"},
        }
        known_terms = {term for terms in group_terms.values() for term in terms}
        log_words = {"log", "logs", "logger", "logging"}
        general_words = {"all", "general", "everything"}
        action_words = {
            "action",
            "add",
            "clear",
            "create",
            "delete",
            "deletion",
            "join",
            "leave",
            "remove",
            "update",
        }
        candidates = []
        for channel in guild.text_channels:
            bot_member = guild.me
            if bot_member is None:
                continue
            permissions = channel.permissions_for(bot_member)
            if not permissions.send_messages or not permissions.embed_links:
                continue

            raw_tokens = set(re.findall(r"[a-z0-9]+", channel.name.lower()))
            tokens = set(raw_tokens)
            has_log_word = bool(raw_tokens & log_words)
            for token in raw_tokens:
                for suffix in ("logging", "logger", "logs", "log"):
                    if not token.endswith(suffix) or token == suffix:
                        continue
                    stem = token[: -len(suffix)]
                    if stem in known_terms or stem in general_words:
                        tokens.add(stem)
                        has_log_word = True
                    break
            if {"auto", "mod"} <= tokens:
                tokens.discard("mod")
                tokens.add("automod")
            if not has_log_word:
                continue

            matched_groups = {group for group, terms in group_terms.items() if terms & tokens}
            is_general = bool(tokens & general_words) or not matched_groups
            is_private = not channel.permissions_for(guild.default_role).view_channel
            candidates.append((channel, tokens, matched_groups, is_general, is_private))

        suggestions = {}
        for event_type in self.event_descriptions:
            group = self._get_default_event_channel_key(event_type)
            meaningful_terms = set(event_type.split("_")) - action_words
            normalized_event = event_type.replace("_", "-")
            choices = []
            for channel, tokens, matched_groups, is_general, is_private in candidates:
                keyword_matches = meaningful_terms & tokens
                if group not in matched_groups and not keyword_matches and not is_general:
                    continue
                normalized_channel = channel.name.lower().replace("_", "-")
                score = 10
                if normalized_event in normalized_channel:
                    score += 100
                if group in matched_groups:
                    score += 50
                score += len(keyword_matches) * 12
                if is_general:
                    score += 5
                if is_private:
                    score += 2
                choices.append((score, -channel.position, -channel.id, channel))
            if choices:
                suggestions[event_type] = max(choices, key=lambda item: item[:3])[3]
        return suggestions

    @staticmethod
    def _yd_channel_options(guild, selected, empty):
        options = [f'<option value="">{html.escape(empty)}</option>']
        for channel in guild.text_channels:
            permissions = channel.permissions_for(guild.me) if guild.me is not None else None
            warning = ""
            if permissions is None or not permissions.send_messages or not permissions.embed_links:
                warning = " ⚠ missing Send Messages/Embed Links"
            options.append(
                f'<option value="{channel.id}"{" selected" if channel.id == selected else ""}>'
                f"#{html.escape(channel.name + warning)}</option>",
            )
        return "".join(options)

    @staticmethod
    def _yd_multi_options(items, selected, prefix=""):
        chosen = {int(item) for item in selected}
        return "".join(
            f'<option value="{item.id}"{" selected" if item.id in chosen else ""}>{prefix}{html.escape(item.name)}</option>'
            for item in items
        )

    @staticmethod
    def _yd_csrf(kwargs):
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'
