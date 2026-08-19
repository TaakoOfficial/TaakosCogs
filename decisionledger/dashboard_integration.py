# ruff: noqa: E501
"""Purpose-built dashboard for DecisionLedger."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, Callable

from redbot.core import commands

if TYPE_CHECKING:
    import discord


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(name=None, description="Inspect decision counts and configure approval separation.", methods=("GET", "POST"))
    async def dashboard_page(self, user: discord.User, guild: discord.Guild, **kwargs: Any):
        member = guild.get_member(user.id)
        if not (
            user.id in getattr(self.bot, "owner_ids", set())
            or (member and await self.bot.is_admin(member))
            or (member and member.guild_permissions.manage_guild)
        ):
            return {"status": 1, "error_title": "Insufficient Permissions", "error_message": "Manage Server is required."}
        conf = self.config.guild(guild)
        notices = []
        if kwargs.get("method", "GET").upper() == "POST":
            data = kwargs.get("data") or {}
            form = (data.get("form") or data.get("json") or {}) if isinstance(data, dict) else data
            raw = form.get("require_separate_approver", "") if hasattr(form, "get") else ""
            raw = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
            await conf.require_separate_approver.set(str(raw).casefold() in {"1", "true", "on", "yes"})
            suggestion_raw = form.get("auto_import_suggestions", "") if hasattr(form, "get") else ""
            suggestion_raw = suggestion_raw[0] if isinstance(suggestion_raw, (list, tuple)) and suggestion_raw else suggestion_raw
            incident_raw = form.get("auto_import_incident_actions", "") if hasattr(form, "get") else ""
            incident_raw = incident_raw[0] if isinstance(incident_raw, (list, tuple)) and incident_raw else incident_raw
            await conf.auto_import_suggestions.set(str(suggestion_raw).casefold() in {"1", "true", "on", "yes"})
            await conf.auto_import_incident_actions.set(str(incident_raw).casefold() in {"1", "true", "on", "yes"})
            quorum_raw = form.get("approval_quorum", 1) if hasattr(form, "get") else 1
            evidence_raw = form.get("required_evidence", 0) if hasattr(form, "get") else 0
            quorum_raw = quorum_raw[0] if isinstance(quorum_raw, (list, tuple)) and quorum_raw else quorum_raw
            evidence_raw = evidence_raw[0] if isinstance(evidence_raw, (list, tuple)) and evidence_raw else evidence_raw
            try:
                quorum = max(1, min(20, int(quorum_raw or 1)))
                evidence = max(0, min(25, int(evidence_raw or 0)))
            except (TypeError, ValueError):
                quorum, evidence = 1, 0
            await conf.approval_quorum.set(quorum)
            await conf.required_evidence.set(evidence)
            notices.append({"message": "DecisionLedger settings saved.", "category": "success"})
        settings = await conf.all()
        counts = dict.fromkeys(("proposed", "accepted", "rejected", "implemented", "superseded"), 0)
        for item in settings["decisions"].values():
            counts[item["status"]] += 1
        review_due = sum(bool(item.get("review_due_at")) for item in settings["decisions"].values())
        csrf = kwargs.get("csrf_token")
        csrf_html = (
            ""
            if not isinstance(csrf, (tuple, list)) or len(csrf) != 2
            else f'<input type="hidden" name="csrf_token" value="{html.escape(str(csrf[1]), quote=True)}">'
        )
        cards = " ".join(f'<span class="card"><b>{count}</b> {status}</span>' for status, count in counts.items())
        checked = " checked" if settings["require_separate_approver"] else ""
        suggestion_checked = " checked" if settings["auto_import_suggestions"] else ""
        incident_checked = " checked" if settings["auto_import_incident_actions"] else ""
        suggestion_status = "loaded" if self.bot.get_cog("SuggestionBox") else "not loaded"
        incident_status = "loaded" if self.bot.get_cog("OpsRoom") else "not loaded"
        reminder = (
            f"every {settings['reminder_interval_hours']} hour(s) in <#{settings['reminder_channel_id']}>"
            if settings["reminder_channel_id"]
            else "disabled"
        )
        source = f'<section><h2>DecisionLedger</h2><p>{cards}</p><p><b>{len(settings["templates"])}</b> templates · <b>{review_due}</b> review cycles · reminders <b>{reminder}</b></p><p>SuggestionBox: <b>{suggestion_status}</b> · OpsRoom: <b>{incident_status}</b></p><form method="POST">{csrf_html}<label><input type="checkbox" name="require_separate_approver" value="1"{checked}> Require a proposer and approver to be different people</label><br><label>Approval quorum <input type="number" min="1" max="20" name="approval_quorum" value="{settings["approval_quorum"]}"></label><br><label>Required evidence links <input type="number" min="0" max="25" name="required_evidence" value="{settings["required_evidence"]}"></label><br><label><input type="checkbox" name="auto_import_suggestions" value="1"{suggestion_checked}> Automatically import approved suggestions</label><br><label><input type="checkbox" name="auto_import_incident_actions" value="1"{incident_checked}> Automatically import incomplete actions when incidents resolve</label><br><button class="btn btn-primary">Save DecisionLedger Settings</button></form></section>'
        return {"status": 0, "notifications": notices, "web_content": {"source": source, "expanded": True}}
