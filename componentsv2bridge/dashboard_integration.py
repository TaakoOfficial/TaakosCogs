"""Red-Web-Dashboard editor and sender for ComponentsV2Bridge."""

from __future__ import annotations

import html
import json
import logging
from typing import Any, Callable

import discord
from redbot.core import commands

from .components import ComponentsV2Error, load_payload, payload_to_view

log = logging.getLogger("red.taakoscogs.componentsv2bridge.dashboard")


def dashboard_page(*args, **kwargs):
    def decorator(func: Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Build, preview, convert, and send Discord Components V2 messages.",
        methods=("GET", "POST"),
    )
    async def dashboard_editor(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs: Any,
    ) -> dict[str, Any]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        if not (is_owner or is_admin or (member and member.guild_permissions.manage_guild)):
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        notifications: list[dict[str, str]] = []
        form = self._dashboard_form(kwargs)
        payload_text = self._dashboard_value(form, "payload") or self._example_payload()
        conversion_type = self._dashboard_value(form, "format", "json").lower()
        selected_channel = self._dashboard_value(form, "channel_id")

        if kwargs.get("method", "GET") == "POST":
            try:
                channel_id = int(selected_channel)
                channel = guild.get_channel(channel_id)
                if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
                    raise ComponentsV2Error("Choose a valid text-capable channel.")
                if member is not None and not is_owner and not channel.permissions_for(member).send_messages:
                    raise ComponentsV2Error("You cannot send messages in that channel.")
                if not channel.permissions_for(guild.me).send_messages:
                    raise ComponentsV2Error("The bot cannot send messages in that channel.")
                view = payload_to_view(load_payload(payload_text, conversion_type))
                await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
            except (ComponentsV2Error, ValueError) as error:
                notifications.append({"message": str(error), "category": "danger"})
            except discord.HTTPException as error:
                notifications.append({"message": f"Discord rejected the message: {error}", "category": "danger"})
            except Exception as error:
                log.exception("Components V2 dashboard send failed")
                notifications.append({"message": f"Could not send the message: {error}", "category": "danger"})
            else:
                notifications.append({"message": f"Components V2 message sent in #{channel.name}.", "category": "success"})

        channels = []
        for channel in guild.channels:
            if (
                isinstance(channel, (discord.TextChannel, discord.VoiceChannel))
                and channel.permissions_for(guild.me).send_messages
            ):
                selected = " selected" if str(channel.id) == selected_channel else ""
                channels.append(
                    f'<option value="{channel.id}"{selected}>{html.escape(channel.name)}</option>',
                )
        source = self._editor_source(
            csrf=self._dashboard_csrf(kwargs),
            payload=payload_text,
            channel_options="".join(channels),
            conversion_type=conversion_type,
        )
        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {"source": source, "expanded": True},
        }

    @staticmethod
    def _dashboard_form(kwargs: dict[str, Any]) -> Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    @staticmethod
    def _dashboard_value(form: Any, key: str, default: str = "") -> str:
        value = form.get(key, default) if hasattr(form, "get") else default
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @staticmethod
    def _dashboard_csrf(kwargs: dict[str, Any]) -> str:
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'

    @staticmethod
    def _example_payload() -> str:
        return json.dumps(
            {
                "flags": 32768,
                "components": [
                    {
                        "type": 17,
                        "accent_color": 5793266,
                        "components": [
                            {"type": 10, "content": "## Components V2"},
                            {"type": 10, "content": "Built with the EmbedUtils bridge."},
                            {"type": 14, "divider": True, "spacing": 1},
                            {
                                "type": 1,
                                "components": [
                                    {
                                        "type": 2,
                                        "style": 5,
                                        "label": "Discord docs",
                                        "url": "https://discord.com/developers/docs/components/reference",
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
            indent=2,
        )

    @staticmethod
    def _editor_source(*, csrf: str, payload: str, channel_options: str, conversion_type: str) -> str:
        json_selected = " selected" if conversion_type != "yaml" else ""
        yaml_selected = " selected" if conversion_type == "yaml" else ""
        escaped_payload = html.escape(payload)
        return f"""
<style>
.cv2-grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(320px,.8fr); gap:1rem; }}
.cv2-card {{ background:var(--bs-body-bg,#fff); border:1px solid rgba(127,127,127,.3); border-radius:.6rem; padding:1rem; }}
.cv2-card textarea {{ width:100%; min-height:520px; font-family:ui-monospace,monospace; font-size:.86rem; }}
.cv2-row {{ display:flex; flex-wrap:wrap; gap:.6rem; margin-top:.8rem; }}
.cv2-row select,.cv2-row button {{ min-height:38px; }}
.cv2-preview {{ background:#313338; color:#dbdee1; border-radius:.5rem; padding:1rem; min-height:180px; }}
.cv2-container {{ border:1px solid #3f4147; border-left:4px solid #5865f2; border-radius:4px; padding:.75rem; margin:.5rem 0; }}
.cv2-text {{ white-space:pre-wrap; margin:.35rem 0; }}
.cv2-separator {{ border-top:1px solid #4e5058; margin:.75rem 0; }}
.cv2-button {{ display:inline-block; background:#4e5058; color:white; padding:.5rem .8rem; border-radius:3px; margin:.25rem; }}
@media(max-width:900px) {{ .cv2-grid {{ grid-template-columns:1fr; }} }}
</style>
<div class="cv2-grid">
  <div class="cv2-card">
    <h3>Components V2 payload</h3>
    <p>Paste native Components V2 JSON/YAML or an EmbedUtils content/embed payload. Mentions are disabled for dashboard sends.</p>
    <form method="POST">
      {csrf}
      <textarea id="cv2-payload" name="payload" spellcheck="false">{escaped_payload}</textarea>
      <div class="cv2-row">
        <select id="cv2-format" name="format">
          <option value="json"{json_selected}>JSON</option>
          <option value="yaml"{yaml_selected}>YAML</option>
        </select>
        <select name="channel_id" required><option value="">Choose a channel</option>{channel_options}</select>
        <button class="btn btn-primary" type="submit">Send Components V2</button>
        <button class="btn btn-secondary" id="cv2-preview-button" type="button">Refresh preview</button>
      </div>
    </form>
  </div>
  <div class="cv2-card">
    <h3>Preview</h3>
    <div id="cv2-preview" class="cv2-preview"></div>
    <p><small>The browser preview is approximate; Discord remains authoritative.</small></p>
  </div>
</div>
<script>
(() => {{
  const input = document.getElementById('cv2-payload');
  const preview = document.getElementById('cv2-preview');
  const escapes = {{'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#039;'}};
  const escapeHtml = value => String(value).replace(/[&<>"']/g, c => escapes[c]);
  function render(items, root) {{
    for (const item of items || []) {{
      if (item.type === 10) root.insertAdjacentHTML('beforeend', `<div class="cv2-text">${{escapeHtml(item.content)}}</div>`);
      else if (item.type === 14) root.insertAdjacentHTML('beforeend', '<div class="cv2-separator"></div>');
      else if (item.type === 17) {{
        const box = document.createElement('div'); box.className = 'cv2-container';
        if (item.accent_color) box.style.borderLeftColor = '#'
          + Number(item.accent_color).toString(16).padStart(6, '0');
        root.appendChild(box); render(item.components, box);
      }}
      else if (item.type === 1) {{
        const row = document.createElement('div'); root.appendChild(row);
        render(item.components, row);
      }}
      else if (item.type === 2) root.insertAdjacentHTML(
        'beforeend', `<span class="cv2-button">${{escapeHtml(item.label || 'Button')}}</span>`
      );
      else if (item.type === 12) for (const media of item.items || []) {{
        const img = document.createElement('img');
        img.src = (media.media || {{}}).url || media.media;
        img.style.maxWidth = '100%'; img.style.borderRadius = '4px';
        root.appendChild(img);
      }}
      else root.insertAdjacentHTML('beforeend', `<div class="cv2-text">Component type ${{escapeHtml(item.type)}}</div>`);
    }}
  }}
  function refresh() {{
    preview.innerHTML='';
    if (document.getElementById('cv2-format').value !== 'json') {{
      preview.textContent = 'YAML preview is rendered after sending; switch to JSON for live preview.';
      return;
    }}
    try {{
      const data = JSON.parse(input.value);
      if (data.components) render(data.components, preview);
      else preview.textContent = 'EmbedUtils payload detected. It will be converted when sent.';
    }}
    catch(error) {{ preview.textContent='JSON error: '+error.message; }}
  }}
  document.getElementById('cv2-preview-button').addEventListener('click',refresh); refresh();
}})();
</script>
"""
