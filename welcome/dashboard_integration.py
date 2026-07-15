"""Red-Web-Dashboard integration for Welcome."""

from __future__ import annotations

import html
import json
import logging
import typing

import discord
from redbot.core import commands

log = logging.getLogger("red.taakoscogs.welcome.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Dashboard integration mixin for Welcome."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register Welcome as a Red-Web-Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Configure Welcome messages, embeds, images, avatar overlays, and previews.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the Welcome dashboard page."""
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
                notifications.append(
                    {"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("Welcome dashboard action failed.")
                notifications.append(
                    {
                        "message": f"Welcome dashboard action failed: {error}",
                        "category": "error",
                    },
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
    ) -> tuple[discord.Member | None, bool]:
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = (
            is_owner
            or is_admin
            or (member is not None and member.guild_permissions.manage_guild)
        )
        return member, can_manage

    def _dashboard_form_data(self, kwargs: dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    def _dashboard_active_tab(self, kwargs, action_tabs, default):
        form_data = self._dashboard_form_data(kwargs)
        selected = self._dash_value(form_data, "active_tab").lower()
        valid = set(action_tabs.values()) | {default}
        return (
            selected
            if selected in valid
            else action_tabs.get(
                self._dash_value(form_data, "action").lower(),
                default,
            )
        )

    def _dashboard_tab_button(self, name: str, label: str, active: str) -> str:
        selected = name == active
        return (
            f'<button type="button" class="dash-tab{" active" if selected else ""}" '
            f'data-tab="{self._h(name)}" role="tab" aria-selected="{str(selected).lower()}" '
            f'tabindex="{0 if selected else -1}">{self._h(label)}</button>'
        )

    @staticmethod
    def _dashboard_tabs_script() -> str:
        return """
        <script>
        (() => {
            const root = document.currentScript.closest("[data-dashboard-tabs]");
            if (!root) return;
            const tabs = Array.from(root.querySelectorAll("[data-tab]"));
            const panels = Array.from(root.querySelectorAll("[data-tab-panel]"));
            const names = new Set(tabs.map((tab) => tab.dataset.tab));
            const activate = (name, updateHash = false) => {
                if (!names.has(name)) return;
                tabs.forEach((tab) => {
                    const selected = tab.dataset.tab === name;
                    tab.classList.toggle("active", selected);
                    tab.setAttribute("aria-selected", selected ? "true" : "false");
                    tab.tabIndex = selected ? 0 : -1;
                });
                panels.forEach((panel) => {
                    const selected = panel.dataset.tabPanel === name;
                    panel.classList.toggle("active", selected);
                    panel.hidden = !selected;
                });
                if (updateHash) history.replaceState(null, "", `#tab-${name}`);
            };
            const fromHash = () => {
                const hash = location.hash.slice(1);
                if (hash.startsWith("tab-") && names.has(hash.slice(4))) return hash.slice(4);
                const section = document.getElementById(hash);
                const panel = section ? section.closest("[data-tab-panel]") : null;
                return panel ? panel.dataset.tabPanel : null;
            };
            tabs.forEach((tab, index) => {
                tab.addEventListener("click", () => activate(tab.dataset.tab, true));
                tab.addEventListener("keydown", (event) => {
                    const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                    if (!offset) return;
                    event.preventDefault();
                    const next = tabs[(index + offset + tabs.length) % tabs.length];
                    next.focus();
                    activate(next.dataset.tab, true);
                });
            });
            root.querySelectorAll("form").forEach((form) => form.addEventListener("submit", () => {
                let input = form.querySelector('input[name="active_tab"]');
                if (!input) {
                    input = document.createElement("input");
                    input.type = "hidden";
                    input.name = "active_tab";
                    form.appendChild(input);
                }
                input.value = root.querySelector("[data-tab].active").dataset.tab;
            }));
            activate(fromHash() || root.querySelector("[data-tab].active").dataset.tab);
        })();
        </script>
        """

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

    def _dash_float(
        self,
        form_data: typing.Any,
        key: str,
        *,
        default: float,
    ) -> float:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return default
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(f"`{key}` must be a number.") from exc

    def _dash_optional_id(self, form_data: typing.Any, key: str) -> int | None:
        value = self._dash_value(form_data, key).strip()
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise commands.BadArgument(
                f"`{key}` must be a Discord ID.") from exc

    def _dash_csrf(self, kwargs: dict[str, typing.Any]) -> str:
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
        member: discord.Member | None,
        action: str,
        form_data: typing.Any,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        if action == "save_settings":
            await self._dashboard_save_settings(guild, member or user, form_data)
            messages.append(
                {"message": "Welcome settings saved.", "category": "success"},
            )

        elif action == "download_image":
            image_data = await self._dashboard_download_image(guild, form_data)
            messages.append(
                {
                    "message": f"Welcome image cached as `{image_data.get('filename')}`.",
                    "category": "success",
                },
            )

        elif action == "clear_image":
            await self.config.guild(guild).image.set(self._empty_image_data())
            messages.append(
                {"message": "Cached welcome image cleared.", "category": "success"},
            )

        elif action == "clear_embed":
            await self.config.guild(guild).embed_json.set("")
            messages.append(
                {"message": "Welcome embed JSON cleared.", "category": "success"},
            )

        elif action == "reset_overlay":
            await self.config.guild(guild).avatar_overlay.set(
                self._default_avatar_overlay(),
            )
            messages.append(
                {"message": "Avatar overlay reset to defaults.", "category": "success"},
            )

        elif action == "test_welcome":
            channel, preview_member = await self._dashboard_test_welcome(
                guild,
                member or user,
                form_data,
            )
            messages.append(
                {
                    "message": f"Welcome preview sent to #{channel.name} for {preview_member}.",
                    "category": "success",
                },
            )

        elif action:
            raise commands.BadArgument("Unknown Welcome dashboard action.")

        return messages

    async def _dashboard_save_settings(
        self,
        guild: discord.Guild,
        preview_user: discord.abc.User,
        form_data: typing.Any,
    ) -> None:
        channel_id = self._dash_optional_id(form_data, "channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel_id and not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument(
                "Welcome channel must be a text channel.")
        enabled = self._dash_bool(form_data, "enabled")
        if enabled and channel is None:
            raise commands.BadArgument(
                "Choose a welcome channel before enabling welcomes.",
            )

        message_template = self._dash_value(form_data, "message_template")
        self._validate_placeholders(message_template)

        image_mode = self._dash_value(
            form_data, "image_mode", "embed").strip().lower()
        if image_mode not in {"embed", "attachment"}:
            raise commands.BadArgument(
                "Image mode must be `embed` or `attachment`.")

        current_overlay = self._normalize_avatar_overlay(
            await self.config.guild(guild).avatar_overlay(),
        )
        avatar_overlay = {
            "enabled": self._dash_bool(form_data, "avatar_overlay_enabled"),
            "x_percent": self._validate_percentage(
                "Center X percent",
                self._dash_float(
                    form_data,
                    "avatar_overlay_x_percent",
                    default=float(current_overlay["x_percent"]),
                ),
                0.0,
                100.0,
            ),
            "y_percent": self._validate_percentage(
                "Center Y percent",
                self._dash_float(
                    form_data,
                    "avatar_overlay_y_percent",
                    default=float(current_overlay["y_percent"]),
                ),
                0.0,
                100.0,
            ),
            "size_percent": self._validate_percentage(
                "Diameter percent",
                self._dash_float(
                    form_data,
                    "avatar_overlay_size_percent",
                    default=float(current_overlay["size_percent"]),
                ),
                1.0,
                100.0,
            ),
        }

        embed_json_text = self._dash_value(form_data, "embed_json").strip()
        stored_embed = ""
        if embed_json_text:
            embed_data = self._dashboard_parse_embed_json(embed_json_text)
            self._validate_placeholders(embed_data)
            preview_member = self._dashboard_preview_member(
                guild, preview_user)
            try:
                self._build_embed(embed_data, preview_member, None, image_mode)
            except Exception as exc:
                raise commands.BadArgument(
                    f"That JSON could not be converted into a Discord embed: {exc}",
                ) from exc
            stored_embed = json.dumps(embed_data)

        guild_conf = self.config.guild(guild)
        await guild_conf.enabled.set(enabled)
        await guild_conf.include_bots.set(self._dash_bool(form_data, "include_bots"))
        await guild_conf.channel_id.set(channel.id if channel else None)
        await guild_conf.message_template.set(message_template)
        await guild_conf.embed_json.set(stored_embed)
        await guild_conf.image_mode.set(image_mode)
        await guild_conf.avatar_overlay.set(avatar_overlay)

    async def _dashboard_download_image(
        self,
        guild: discord.Guild,
        form_data: typing.Any,
    ) -> dict[str, str]:
        url = self._dash_value(form_data, "image_url").strip()
        if not url:
            raise commands.BadArgument("Provide an image URL.")
        image_data = await self._download_image(url)
        await self.config.guild(guild).image.set(image_data)
        return image_data

    async def _dashboard_test_welcome(
        self,
        guild: discord.Guild,
        preview_user: discord.abc.User,
        form_data: typing.Any,
    ) -> tuple[discord.TextChannel, discord.Member]:
        settings = await self._get_guild_settings(guild)
        channel_id = self._dash_optional_id(
            form_data,
            "test_channel_id",
        ) or settings.get("channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            raise commands.BadArgument(
                "Choose a text channel for the welcome preview.")

        member_id = self._dash_optional_id(form_data, "test_member_id")
        member = (
            guild.get_member(member_id)
            if member_id
            else self._dashboard_preview_member(guild, preview_user)
        )
        if not isinstance(member, discord.Member):
            raise commands.BadArgument(
                "Choose a server member for the welcome preview.",
            )

        await self._send_welcome_message(channel, member, settings)
        return channel, member

    async def _dashboard_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, typing.Any],
    ) -> str:
        settings = await self._get_guild_settings(guild)
        csrf = self._dash_csrf(kwargs)
        image_data = settings.get("image") or self._empty_image_data()
        avatar_overlay = (
            settings.get("avatar_overlay") or self._default_avatar_overlay()
        )
        channel = guild.get_channel(settings.get("channel_id"))
        embed_json_text = (
            json.dumps(settings.get("embed_json"), indent=2)
            if settings.get("embed_json")
            else ""
        )
        active_tab = self._dashboard_active_tab(
            kwargs,
            {
                "save_settings": "settings",
                "clear_embed": "settings",
                "reset_overlay": "settings",
                "download_image": "image",
                "clear_image": "image",
                "test_welcome": "preview",
            },
            "settings",
        )

        return f"""
        <style>
            .wel-wrap {{ max-width: 1180px; margin: 0 auto; color: #e5e7eb; }}
            .wel-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
            .wel-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;
            margin-bottom: 12px; }}
            .wel-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 16px;
            margin-bottom: 16px; }}
            .wel-card h2, .wel-card h3 {{ margin: 0 0 12px 0; color: #f9fafb; }}
            .wel-muted {{ color: #9ca3af; }}
            .wel-stat {{ font-size: 1.5rem; font-weight: 700; color: #f9fafb; }}
            .wel-field label {{ display: block; font-weight: 600; margin-bottom: 4px; color: #d1d5db; }}
            .wel-field input, .wel-field select, .wel-field textarea {{
                width: 100%; min-width: 0; max-width: 100%; box-sizing: border-box; border: 1px solid #4b5563; border-radius: 6px;
                background: #111827; color: #f9fafb; padding: 8px; min-height: 38px;
            }}
            .wel-field textarea {{ min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
            .wel-check {{ display: flex; align-items: center; gap: 8px; margin: 6px 0; color: #d1d5db; }}
            .wel-check input {{ width: auto; }}
            .wel-btn {{ background: #2563eb; color: white; border: 0; border-radius: 6px; padding: 9px 14px; cursor:
            pointer; font-weight: 700; }}
            .wel-btn.secondary {{ background: #4b5563; }}
            .wel-btn.danger {{ background: #dc2626; }}
            .dash-tabs {{ display: flex; gap: 4px; overflow-x: auto; position: sticky; top: 0; z-index: 10; margin: 0 0
            16px; padding: 5px; background: #111827; border: 1px solid #374151; border-radius: 8px; }}
            .dash-tab {{ flex: 0 0 auto; border: 0; border-radius: 6px; padding: 9px 13px; background: transparent;
            color: #9ca3af; cursor: pointer; font-weight: 700; white-space: nowrap; }}
            .dash-tab:hover {{ background: #1f2937; color: #f9fafb; }}
            .dash-tab.active {{ background: #2563eb; color: white; }}
            .dash-panel {{ display: none; }} .dash-panel.active {{ display: block; }}
            .wel-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
            .wel-table th, .wel-table td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left;
            vertical-align: top; }}
            .wel-table th {{ color: #d1d5db; }}
            .wel-inline {{ display: inline; }}
        </style>
        <div class="wel-wrap" data-dashboard-tabs="1">
            <div class="wel-card">
                <h2>Welcome Dashboard</h2>
                <div class="wel-grid">
                    <div><div class="wel-muted">Enabled</div><div class="wel-stat">{"Yes" if settings.get("enabled")
                    else "No"}</div></div>
                    <div><div class="wel-muted">Channel</div><div class="wel-stat">{self._h("#" + channel.name if
                    channel else "Not Set")}</div></div>
                    <div><div class="wel-muted">Embed JSON</div><div class="wel-stat">{"Yes" if
                    settings.get("embed_json") else "No"}</div></div>
                    <div><div class="wel-muted">Cached Image</div><div class="wel-stat">{"Yes" if
                    image_data.get("data_base64") else "No"}</div></div>
                </div>
            </div>
            <div class="dash-tabs" role="tablist" aria-label="Welcome sections">
                {self._dashboard_tab_button("settings", "Settings", active_tab)}
                {self._dashboard_tab_button("image", "Image", active_tab)}
                {self._dashboard_tab_button("preview", "Preview", active_tab)}
                {self._dashboard_tab_button("reference", "Placeholders", active_tab)}
            </div>
            <section class="dash-panel{" active" if active_tab == "settings" else ""}"
            data-tab-panel="settings">{self._dashboard_settings_section(guild, settings, avatar_overlay,
            embed_json_text, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "image" else ""}"
            data-tab-panel="image">{self._dashboard_image_section(image_data, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "preview" else ""}"
            data-tab-panel="preview">{self._dashboard_test_section(guild, settings, csrf)}</section>
            <section class="dash-panel{" active" if active_tab == "reference" else ""}"
            data-tab-panel="reference">{self._dashboard_placeholders_section()}</section>
            {self._dashboard_tabs_script()}
        </div>
        """

    def _dashboard_settings_section(
        self,
        guild: discord.Guild,
        settings: dict[str, typing.Any],
        avatar_overlay: dict[str, typing.Any],
        embed_json_text: str,
        csrf: str,
    ) -> str:
        return f"""
        <div id="settings" class="wel-card">
            <h3>Settings</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="save_settings">
                <div class="wel-grid">
                    <div>
                        <label class="wel-check"><input type="checkbox" name="enabled" value="1"
                        {self._checked(settings.get("enabled"))}> Enabled</label>
                        <label class="wel-check"><input type="checkbox" name="include_bots" value="1"
                        {self._checked(settings.get("include_bots"))}> Include Bots</label>
                        <label class="wel-check"><input type="checkbox" name="avatar_overlay_enabled" value="1"
                        {self._checked(avatar_overlay.get("enabled"))}> Avatar Overlay</label>
                    </div>
                    <div class="wel-row">
                        {self._channel_select(guild, "channel_id", "Welcome Channel", settings.get("channel_id"))}
                        <div class="wel-field"><label>Image Mode</label><select name="image_mode">{self._option("embed",
                         "Embed Image", settings.get("image_mode"))}{self._option("attachment", "Attachment",
                        settings.get("image_mode"))}</select></div>
                    </div>
                </div>
                {self._textarea("message_template", "Message Template", settings.get("message_template") or "", rows=4)}
                <div class="wel-row">
                    {self._input("avatar_overlay_x_percent", "Avatar Center X Percent", avatar_overlay.get("x_percent",
                    82.0), "number", min_value=0, max_value=100, step="0.1")}
                    {self._input("avatar_overlay_y_percent", "Avatar Center Y Percent", avatar_overlay.get("y_percent",
                    52.0), "number", min_value=0, max_value=100, step="0.1")}
                    {self._input("avatar_overlay_size_percent", "Avatar Diameter Percent",
                    avatar_overlay.get("size_percent", 17.0), "number", min_value=1, max_value=100, step="0.1")}
                </div>
                <div id="embed" class="wel-field">
                    <label>Embed JSON</label>
                    <textarea name="embed_json" rows="14">{self._h(embed_json_text)}</textarea>
                </div>
                <button class="wel-btn" type="submit">Save Settings</button>
            </form>
            <form class="wel-inline" method="POST">
                {csrf}
                <input type="hidden" name="action" value="clear_embed">
                <button class="wel-btn danger" type="submit">Clear Embed JSON</button>
            </form>
            <form class="wel-inline" method="POST">
                {csrf}
                <input type="hidden" name="action" value="reset_overlay">
                <button class="wel-btn secondary" type="submit">Reset Avatar Overlay</button>
            </form>
        </div>
        """

    def _dashboard_image_section(
        self,
        image_data: dict[str, typing.Any],
        csrf: str,
    ) -> str:
        filename = self._h(image_data.get("filename") or "Not set")
        content_type = self._h(image_data.get("content_type") or "Not set")
        source_url = self._h(image_data.get("source_url") or "Not set")
        return f"""
        <div id="image" class="wel-card">
            <h3>Image</h3>
            <div class="wel-grid">
                <div><div class="wel-muted">Filename</div><div>{filename}</div></div>
                <div><div class="wel-muted">Content Type</div><div>{content_type}</div></div>
                <div><div class="wel-muted">Source URL</div><div>{source_url}</div></div>
            </div>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="download_image">
                {self._input("image_url", "Image URL", image_data.get("source_url") or "")}
                <button class="wel-btn" type="submit">Download and Cache Image</button>
            </form>
            <form class="wel-inline" method="POST">
                {csrf}
                <input type="hidden" name="action" value="clear_image">
                <button class="wel-btn danger" type="submit">Clear Cached Image</button>
            </form>
        </div>
        """

    def _dashboard_test_section(
        self,
        guild: discord.Guild,
        settings: dict[str, typing.Any],
        csrf: str,
    ) -> str:
        return f"""
        <div id="test" class="wel-card">
            <h3>Preview</h3>
            <form method="POST">
                {csrf}
                <input type="hidden" name="action" value="test_welcome">
                <div class="wel-row">
                    {self._channel_select(guild, "test_channel_id", "Preview Channel", settings.get("channel_id"))}
                    {self._input("test_member_id", "Preview Member ID", "")}
                </div>
                <button class="wel-btn secondary" type="submit">Send Preview</button>
            </form>
        </div>
        """

    def _dashboard_placeholders_section(self) -> str:
        member_rows = "".join(
            f"<tr><td>{self._h('{member.' + name + '}')}</td><td>{self._h(description)}</td></tr>"
            for name, description in self.MEMBER_PLACEHOLDERS.items()
        )
        guild_rows = "".join(
            f"<tr><td>{self._h('{guild.' + name + '}')}</td><td>{self._h(description)}</td></tr>"
            for name, description in self.GUILD_PLACEHOLDERS.items()
        )
        return f"""
        <div id="placeholders" class="wel-card">
            <h3>Placeholders</h3>
            <div class="wel-grid">
                <div>
                    <h3>Member</h3>
                    <table class="wel-table"><tbody>{member_rows}</tbody></table>
                </div>
                <div>
                    <h3>Guild</h3>
                    <table class="wel-table"><tbody>{guild_rows}</tbody></table>
                </div>
            </div>
        </div>
        """

    def _dashboard_parse_embed_json(self, raw_json: str) -> dict[str, typing.Any]:
        payload = raw_json.strip()
        if payload.startswith("```") and payload.endswith("```"):
            payload = "\n".join(payload.splitlines()[1:-1]).strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise commands.BadArgument(
                f"Invalid JSON near line {exc.lineno}, column {exc.colno}: {exc.msg}",
            ) from exc
        if not isinstance(parsed, dict):
            raise commands.BadArgument(
                "Embed JSON must be a single JSON object.")
        embed_object = self._extract_embed_object(parsed)
        cleaned = self._sanitize_embed_dict(embed_object)
        return self._normalise_embed_dict(cleaned)

    def _validate_placeholders(self, value: typing.Any) -> None:
        unknown = self._find_unknown_placeholders(value)
        if unknown:
            unknown_text = ", ".join(f"`{{{name}}}`" for name in unknown)
            raise commands.BadArgument(f"Unknown placeholders: {unknown_text}")

    def _dashboard_preview_member(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
    ) -> discord.Member:
        member = guild.get_member(user.id)
        if member is not None:
            return member
        if guild.me is not None:
            return guild.me
        raise commands.CommandError(
            "I could not resolve a server member for the preview.",
        )

    def _channel_select(
        self,
        guild: discord.Guild,
        name: str,
        label: str,
        selected: typing.Any,
    ) -> str:
        options = ['<option value="">None</option>']
        for channel in sorted(guild.text_channels, key=lambda item: item.name.lower()):
            options.append(
                f'<option value="{channel.id}" {self._selected(channel.id, selected)}>#{self._h(channel.name)}</option>',
            )
        return (
            f'<div class="wel-field"><label>{self._h(label)}</label>'
            f'<select name="{self._h(name)}">{"".join(options)}</select></div>'
        )

    def _input(
        self,
        name: str,
        label: str,
        value: typing.Any,
        input_type: str = "text",
        *,
        min_value: int | float | None = None,
        max_value: int | float | None = None,
        step: str | None = None,
    ) -> str:
        attrs = []
        if min_value is not None:
            attrs.append(f'min="{min_value}"')
        if max_value is not None:
            attrs.append(f'max="{max_value}"')
        if step is not None:
            attrs.append(f'step="{self._h(step)}"')
        return (
            f'<div class="wel-field"><label>{self._h(label)}</label>'
            f'<input type="{self._h(input_type)}" name="{self._h(name)}" '
            f'value="{self._h(value)}" {" ".join(attrs)}></div>'
        )

    def _textarea(
        self,
        name: str,
        label: str,
        value: typing.Any,
        *,
        rows: int = 4,
    ) -> str:
        return (
            f'<div class="wel-field"><label>{self._h(label)}</label>'
            f'<textarea name="{self._h(name)}" rows="{rows}">{self._h(value)}</textarea></div>'
        )

    def _option(self, value: typing.Any, label: str, selected: typing.Any) -> str:
        return f'<option value="{self._h(value)}" {self._selected(value, selected)}>{self._h(label)}</option>'

    def _selected(self, value: typing.Any, selected: typing.Any) -> str:
        return "selected" if str(value) == str(selected) else ""

    def _checked(self, value: typing.Any) -> str:
        return "checked" if bool(value) else ""

    def _h(self, value: typing.Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)
