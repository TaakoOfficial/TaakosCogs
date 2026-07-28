# ruff: noqa: E501
"""Purpose-built Red-Web-Dashboard integration for SpinWheel."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets
import typing

from redbot.core import commands

if typing.TYPE_CHECKING:
    import discord

log = logging.getLogger("red.taakoscogs.spinwheel.dashboard")


def dashboard_page(*args, **kwargs):
    """Dashboard page decorator compatible with Red-Web-Dashboard."""

    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func

    return decorator


class DashboardIntegration:
    """Standalone visual editor and spinner for SpinWheel."""

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register SpinWheel as a Dashboard third party."""
        handler = dashboard_cog.rpc.third_parties_handler
        try:
            handler.add_third_party(self, overwrite=True)
        except TypeError:
            handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="Build, style, save, and spin animated wheels.",
        methods=("GET", "POST"),
    )
    async def dashboard_page(
        self,
        user: discord.User,
        guild: discord.Guild,
        **kwargs,
    ) -> dict[str, typing.Any]:
        """Render and process the SpinWheel dashboard."""
        member = guild.get_member(user.id)
        is_owner = user.id in getattr(self.bot, "owner_ids", set())
        is_admin = member is not None and await self.bot.is_admin(member)
        can_manage = is_owner or is_admin or (member is not None and member.guild_permissions.manage_guild)
        if not can_manage:
            return {
                "status": 1,
                "error_title": "Insufficient Permissions",
                "error_message": "You need Manage Server, Red admin, or bot owner access.",
            }

        form_data = self._sw_form_data(kwargs)
        notifications: list[dict[str, str]] = []
        spin_result: dict[str, typing.Any] | None = None
        if str(kwargs.get("method", "GET")).upper() == "POST":
            try:
                message, spin_result = await self._sw_handle_action(
                    guild,
                    self._sw_value(form_data, "action"),
                    form_data,
                )
            except commands.CommandError as error:
                notifications.append({"message": str(error), "category": "error"})
            except Exception as error:
                log.exception("SpinWheel dashboard action failed.")
                notifications.append(
                    {"message": f"SpinWheel action failed: {error}", "category": "error"},
                )
            else:
                notifications.append({"message": message, "category": "success"})

        return {
            "status": 0,
            "notifications": notifications,
            "web_content": {
                "source": await self._sw_source(guild, kwargs, spin_result),
                "expanded": True,
            },
        }

    @staticmethod
    def _sw_form_data(kwargs: dict[str, typing.Any]) -> typing.Any:
        data = kwargs.get("data") or {}
        if isinstance(data, dict) and ("form" in data or "json" in data):
            return data.get("form") or data.get("json") or {}
        return data

    @staticmethod
    def _sw_value(data: typing.Any, key: str, default: str = "") -> str:
        if not hasattr(data, "get"):
            return default
        value = data.get(key, default)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return default if value is None else str(value)

    @classmethod
    def _sw_bool(cls, data: typing.Any, key: str) -> bool:
        if not hasattr(data, "__contains__") or key not in data:
            return False
        return cls._sw_value(data, key, "1").lower() not in {"", "0", "false", "no", "off"}

    @staticmethod
    def _sw_csrf(kwargs: dict[str, typing.Any]) -> str:
        token = kwargs.get("csrf_token")
        if not isinstance(token, (tuple, list)) or len(token) != 2:
            return ""
        return f'<input type="hidden" name="csrf_token" value="{html.escape(str(token[1]), quote=True)}">'

    @staticmethod
    def _sw_h(value: typing.Any) -> str:
        return html.escape(str(value), quote=True)

    async def _sw_handle_action(
        self,
        guild: discord.Guild,
        action: str,
        data: typing.Any,
    ) -> tuple[str, dict[str, typing.Any] | None]:
        action = action.casefold().strip()
        conf = self.config.guild(guild)
        if action == "save_settings":
            try:
                maximum = int(self._sw_value(data, "max_entries", "40"))
            except ValueError as exc:
                raise commands.BadArgument("Maximum entries must be a whole number.") from exc
            theme = self._sw_value(data, "default_theme", "rainbow").casefold()
            if theme == "custom":
                raise commands.BadArgument("Choose a built-in theme for instant wheels.")
            self._theme_colors(theme)
            await conf.allow_member_spins.set(self._sw_bool(data, "allow_member_spins"))
            await conf.max_entries.set(max(2, min(maximum, self.ABSOLUTE_MAX_ENTRIES)))
            await conf.default_theme.set(theme)
            return "Wheel settings saved.", None

        if action == "save_wheel":
            name = self._sw_value(data, "name")
            entries = await self._validated_entries(guild, self._sw_value(data, "entries"))
            theme = self._sw_value(data, "theme", "rainbow").casefold()
            colors = self.parse_colors(self._sw_value(data, "colors")) if theme == "custom" else None
            clean = await self._create_or_update_wheel(
                guild,
                name,
                entries,
                theme=theme,
                colors=colors,
                remove_winner=self._sw_bool(data, "remove_winner"),
            )
            if self._sw_bool(data, "make_default"):
                await conf.default_wheel.set(clean)
            return f"Saved {self._display_name(clean)} with {len(entries)} entries.", None

        name = self._clean_name(self._sw_value(data, "name"))
        if action == "set_default":
            await self._saved_wheel(guild, name)
            await conf.default_wheel.set(name)
            return f"{self._display_name(name)} is now the default wheel.", None

        if action == "delete_wheel":
            if self._sw_value(data, "confirmation").upper() != "DELETE":
                raise commands.BadArgument("Type DELETE to confirm removing the wheel.")
            async with conf.wheels() as wheels:
                if wheels.pop(name, None) is None:
                    raise commands.BadArgument("That saved wheel was not found.")
            if await conf.default_wheel() == name:
                await conf.default_wheel.set(None)
            return f"Deleted {self._display_name(name)}.", None

        if action == "spin_wheel":
            lock = self._guild_spin_locks.setdefault(guild.id, asyncio.Lock())
            async with lock, conf.wheels() as wheels:
                wheel = wheels.get(name)
                if wheel is None:
                    raise commands.BadArgument("That saved wheel was not found.")
                entries = [str(item) for item in wheel.get("entries", [])]
                if len(entries) < 2:
                    raise commands.BadArgument("That wheel needs at least two entries.")
                winner_index = secrets.randbelow(len(entries))
                winner = entries[winner_index]
                wheel["spin_count"] = int(wheel.get("spin_count", 0)) + 1
                wheel["last_winner"] = winner
                if wheel.get("remove_winner") and len(entries) > 2:
                    remaining = list(entries)
                    remaining.pop(winner_index)
                    wheel["entries"] = remaining
                palette = self._theme_colors(
                    str(wheel.get("theme", "rainbow")),
                    [str(color) for color in wheel.get("colors", [])],
                )
            return f"The wheel selected {winner}!", {
                "name": name,
                "winner": winner,
                "winner_index": winner_index,
                "entry_count": len(entries),
                "colors": palette,
                "turns": 5 + secrets.randbelow(4),
            }

        raise commands.BadArgument("Unknown dashboard action.")

    def _sw_theme_options(self, selected: str, *, allow_custom: bool = True) -> str:
        names = (
            "rainbow",
            "ocean",
            "sunset",
            "forest",
            "candy",
            "pastel",
            "neon",
            "midnight",
        )
        if allow_custom:
            names += ("custom",)
        return "".join(
            f'<option value="{name}"{" selected" if name == selected else ""}>{name.title()}</option>' for name in names
        )

    @staticmethod
    def _sw_gradient(colors: typing.Sequence[str], count: int) -> str:
        stops = []
        for index in range(count):
            start = (index / count) * 100
            end = ((index + 1) / count) * 100
            color = colors[index % len(colors)]
            stops.append(f"{color} {start:.3f}% {end:.3f}%")
        return "conic-gradient(from 90deg, " + ",".join(stops) + ")"

    async def _sw_source(
        self,
        guild: discord.Guild,
        kwargs: dict[str, typing.Any],
        result: dict[str, typing.Any] | None,
    ) -> str:
        conf = self.config.guild(guild)
        settings = await conf.all()
        wheels = settings.get("wheels", {})
        default_name = settings.get("default_wheel")
        csrf = self._sw_csrf(kwargs)
        h = self._sw_h

        result_html = ""
        if result is not None:
            segment = 360 / int(result["entry_count"])
            center = (int(result["winner_index"]) + 0.5) * segment
            rotation = (int(result["turns"]) * 360) - center
            gradient = self._sw_gradient(result["colors"], int(result["entry_count"]))
            result_html = f"""
            <section class="sw-result" aria-live="polite">
              <div class="sw-stage">
                <div class="sw-wheel sw-spinning" style="--wheel:{h(gradient)};--stop:{rotation:.3f}deg"></div>
                <div class="sw-hub">★</div><div class="sw-pointer"></div>
              </div>
              <div><span class="sw-kicker">The wheel chose</span><h2>{h(result["winner"])}</h2>
              <p>{h(self._display_name(result["name"]))} · secure random selection</p></div>
            </section>"""

        wheel_cards = []
        for name, wheel in sorted(wheels.items()):
            entries = [str(item) for item in wheel.get("entries", [])]
            theme = str(wheel.get("theme", "rainbow"))
            colors = [str(item) for item in wheel.get("colors", [])]
            palette = self._theme_colors(theme, colors)
            gradient = self._sw_gradient(palette, max(2, len(entries)))
            default_badge = '<span class="sw-badge">Default</span>' if name == default_name else ""
            removal_badge = '<span class="sw-badge muted">Remove winners</span>' if wheel.get("remove_winner") else ""
            entry_text = "\n".join(entries)
            color_text = " ".join(colors)
            wheel_cards.append(f"""
            <article class="sw-card sw-saved">
              <div class="sw-card-head">
                <div class="sw-mini" style="--wheel:{h(gradient)}"></div>
                <div><h3>{h(self._display_name(name))}</h3><p>{len(entries)} entries · {int(wheel.get("spin_count", 0))} spins</p></div>
                <div class="sw-badges">{default_badge}{removal_badge}</div>
              </div>
              <p class="sw-last">Last winner: <strong>{h(wheel.get("last_winner") or "No spins yet")}</strong></p>
              <form method="post" class="sw-inline">
                {csrf}<input type="hidden" name="action" value="spin_wheel"><input type="hidden" name="name" value="{h(name)}">
                <button class="sw-primary" type="submit">Spin this wheel</button>
              </form>
              <details><summary>Edit wheel</summary>
                <form method="post" class="sw-form">
                  {csrf}<input type="hidden" name="action" value="save_wheel"><input type="hidden" name="name" value="{h(name)}">
                  <label class="wide">Entries <span>one per line, or separated by commas</span><textarea name="entries" rows="7" required>{h(entry_text)}</textarea></label>
                  <label>Theme<select name="theme">{self._sw_theme_options(theme)}</select></label>
                  <label>Custom hex colors<input name="colors" value="{h(color_text)}" placeholder="#ef4444 #3b82f6"></label>
                  <label class="sw-check"><input type="checkbox" name="remove_winner" value="1"{" checked" if wheel.get("remove_winner") else ""}> Remove each winner after spinning</label>
                  <button class="sw-secondary" type="submit">Save changes</button>
                </form>
                <div class="sw-danger-row">
                  <form method="post">{csrf}<input type="hidden" name="action" value="set_default"><input type="hidden" name="name" value="{h(name)}"><button type="submit">Make default</button></form>
                  <form method="post" class="sw-delete">{csrf}<input type="hidden" name="action" value="delete_wheel"><input type="hidden" name="name" value="{h(name)}"><input name="confirmation" placeholder="Type DELETE" required><button type="submit">Delete</button></form>
                </div>
              </details>
            </article>""")
        saved_html = "".join(wheel_cards) or '<div class="sw-empty">No saved wheels yet. Build your first one below.</div>'

        member_checked = " checked" if settings.get("allow_member_spins", True) else ""
        return f"""
        <div class="spinwheel-dashboard">
          <style>
            .spinwheel-dashboard{{--ink:#f8fafc;--muted:#a8b3c7;--panel:#121a2a;--panel2:#182338;--line:#334155;--accent:#8b5cf6;color:var(--ink);max-width:1320px;margin:auto;font-family:Inter,system-ui,sans-serif}}
            .spinwheel-dashboard *{{box-sizing:border-box}}.sw-hero{{padding:32px;border-radius:24px;background:radial-gradient(circle at 85% 10%,#7c3aed55,transparent 38%),linear-gradient(135deg,#111827,#172554);border:1px solid #475569;margin-bottom:22px}}
            .sw-hero h1{{font-size:clamp(2rem,5vw,3.7rem);margin:0 0 8px;line-height:1}}.sw-hero p,.sw-card p{{color:var(--muted)}}.sw-kicker{{color:#c4b5fd;text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:.76rem}}
            .sw-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}}.sw-card,.sw-result{{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 18px 45px #02061733}}
            .sw-card h2,.sw-card h3,.sw-result h2{{margin:4px 0}}.sw-card-head{{display:flex;gap:14px;align-items:center}}.sw-card-head>div:nth-child(2){{flex:1}}.sw-card-head p{{margin:3px 0}}
            .sw-form{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}}.sw-form label{{font-weight:700;font-size:.9rem}}.sw-form label span{{display:block;color:var(--muted);font-weight:400;margin:3px 0 7px}}.sw-form .wide,.sw-form button,.sw-check{{grid-column:1/-1}}
            .spinwheel-dashboard input,.spinwheel-dashboard textarea,.spinwheel-dashboard select{{width:100%;margin-top:7px;padding:11px 12px;border-radius:10px;border:1px solid #475569;background:#0b1220;color:var(--ink)}}.spinwheel-dashboard textarea{{resize:vertical}}
            .sw-check{{display:flex;align-items:center;gap:8px!important;padding:10px 0}}.sw-check input{{width:auto;margin:0}}button{{border:1px solid #64748b;background:#26344d;color:white;padding:11px 16px;border-radius:10px;font-weight:800;cursor:pointer}}button:hover{{filter:brightness(1.14)}}
            .sw-primary{{width:100%;background:linear-gradient(135deg,#7c3aed,#2563eb);border:0}}.sw-secondary{{background:#334155}}.sw-section-title{{display:flex;justify-content:space-between;align-items:end;margin:30px 2px 13px}}.sw-section-title h2{{margin:0}}
            .sw-mini{{width:68px;height:68px;flex:0 0 68px;border-radius:50%;background:var(--wheel);border:5px solid #e2e8f0;box-shadow:0 0 0 3px #334155}}.sw-badges{{display:flex;gap:5px;flex-wrap:wrap;justify-content:end}}.sw-badge{{background:#6d28d9;padding:5px 8px;border-radius:99px;font-size:.7rem;font-weight:800}}.sw-badge.muted{{background:#334155}}
            .sw-last{{border-top:1px solid #29364d;padding-top:13px}}details{{border-top:1px solid #29364d;margin-top:14px;padding-top:13px}}summary{{cursor:pointer;color:#c4b5fd;font-weight:800}}.sw-danger-row{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;margin-top:14px}}.sw-delete{{display:flex;gap:7px}}.sw-delete input{{margin:0;width:130px}}.sw-delete button{{background:#7f1d1d;border-color:#ef4444}}
            .sw-result{{display:flex;align-items:center;justify-content:center;gap:34px;margin-bottom:22px;background:linear-gradient(135deg,#1e1b4b,#121a2a)}}.sw-result h2{{font-size:2.3rem}}.sw-stage{{width:250px;height:250px;position:relative;flex:0 0 250px}}.sw-wheel{{position:absolute;inset:8px;border-radius:50%;background:var(--wheel);border:7px solid #f8fafc;box-shadow:0 0 0 4px #475569,0 18px 40px #0008}}.sw-spinning{{animation:sw-spin 4.8s cubic-bezier(.12,.64,.12,1) both}}.sw-hub{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:grid;place-items:center;width:52px;height:52px;border-radius:50%;background:#f8fafc;color:#f59e0b;font-size:1.5rem;z-index:3}}.sw-pointer{{position:absolute;right:-7px;top:106px;width:0;height:0;border-top:19px solid transparent;border-bottom:19px solid transparent;border-right:42px solid #fbbf24;z-index:4;filter:drop-shadow(0 3px 2px #0008)}}
            @keyframes sw-spin{{from{{transform:rotate(0)}}to{{transform:rotate(var(--stop))}}}}.sw-empty{{padding:28px;border:1px dashed #64748b;border-radius:16px;color:var(--muted)}}
            @media(max-width:650px){{.sw-result{{flex-direction:column;text-align:center}}.sw-form{{grid-template-columns:1fr}}.sw-stage{{transform:scale(.86);margin:-14px}}}}
            @media(prefers-reduced-motion:reduce){{.sw-spinning{{animation-duration:.01ms}}}}
          </style>
          <header class="sw-hero"><span class="sw-kicker">SpinWheel for {h(guild.name)}</span><h1>Make the choice fun.</h1><p>Build colorful reusable wheels, spin them in Discord or right here, and let secure randomness choose the winner.</p></header>
          {result_html}
          <section class="sw-card">
            <span class="sw-kicker">Server defaults</span><h2>Who can spin and how big?</h2>
            <form method="post" class="sw-form">{csrf}<input type="hidden" name="action" value="save_settings">
              <label>Instant-wheel theme<select name="default_theme">{self._sw_theme_options(str(settings.get("default_theme", "rainbow")), allow_custom=False)}</select></label>
              <label>Maximum entries<input type="number" name="max_entries" min="2" max="{self.ABSOLUTE_MAX_ENTRIES}" value="{int(settings.get("max_entries", 40))}"></label>
              <label class="sw-check"><input type="checkbox" name="allow_member_spins" value="1"{member_checked}> Allow regular members to spin wheels</label>
              <button class="sw-secondary" type="submit">Save server settings</button>
            </form>
          </section>
          <div class="sw-section-title"><div><span class="sw-kicker">Wheel library</span><h2>Saved wheels</h2></div><span>{len(wheels)} total</span></div>
          <section class="sw-grid">{saved_html}</section>
          <div class="sw-section-title"><div><span class="sw-kicker">Wheel builder</span><h2>Create a new wheel</h2></div></div>
          <section class="sw-card">
            <form method="post" class="sw-form">{csrf}<input type="hidden" name="action" value="save_wheel">
              <label>Wheel name<input name="name" maxlength="50" placeholder="Movie night" required></label>
              <label>Theme<select name="theme">{self._sw_theme_options(str(settings.get("default_theme", "rainbow")))}</select></label>
              <label class="wide">Entries <span>one per line, or separated by commas</span><textarea name="entries" rows="9" placeholder="Dune\nEverything Everywhere All at Once\nThe Princess Bride" required></textarea></label>
              <label class="wide">Custom hex colors <span>used when Custom is selected; provide at least two</span><input name="colors" placeholder="#ef4444 #f59e0b #3b82f6 #8b5cf6"></label>
              <label class="sw-check"><input type="checkbox" name="remove_winner" value="1"> Remove each winner after spinning</label>
              <label class="sw-check"><input type="checkbox" name="make_default" value="1"> Make this the default wheel</label>
              <button class="sw-primary" type="submit">Save wheel</button>
            </form>
          </section>
        </div>"""
