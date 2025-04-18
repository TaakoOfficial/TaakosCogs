from redbot.core import Config
import discord
import wtforms

class YALCDashboardIntegration(commands.Cog):
    """Dashboard integration for YALC."""
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        """Register YALC as a third party with the dashboard."""
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="View and edit YALC logging status and settings.",
        methods=("GET",),
    )
    async def dashboard_main(self, guild: typing.Optional[discord.Guild] = None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard main page for YALC."""
        try:
            if not guild:
                return {"status": 0, "web_content": {"source": "<h4>No guild selected.</h4>"}}
            config = await self.bot.get_cog("YALC").config.guild(guild).all()
            events = config.get("events", {})
            event_lines = [f"<li><b>{k}</b>: {'✅' if v else '❌'}</li>" for k, v in events.items()]
            html = f"""
            <h3>YALC Logging Status for {guild.name}</h3>
            <ul>{''.join(event_lines)}</ul>
            <p>
                <a href='events'>Edit Events</a> |
                <a href='channels'>Edit Log Channels</a> |
                <a href='tupperbox'>Tupperbox Settings</a>
            </p>
            """
            return {"status": 0, "web_content": {"source": html}}
        except Exception as e:
            return {"status": 1, "error_title": "Error", "error_message": str(e)}

    @dashboard_page(
        name="events",
        description="Enable or disable logging for each event.",
        methods=("GET", "POST"),
    )
    async def dashboard_events(self, guild: typing.Optional[discord.Guild] = None, Form=None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard page to enable/disable events."""
        try:
            if not guild:
                return {"status": 0, "web_content": {"source": "<h4>No guild selected.</h4>"}}
            yalc = self.bot.get_cog("YALC")
            event_descriptions = getattr(yalc, "event_descriptions", {})
            config = await yalc.config.guild(guild).all()
            events = config.get("events", {})
            class EventsForm(Form):
                pass
            for event, (_, desc) in event_descriptions.items():
                setattr(EventsForm, event, wtforms.BooleanField(desc, default=events.get(event, False)))
            setattr(EventsForm, "submit", wtforms.SubmitField("Save Changes"))
            form = EventsForm()
            if form.validate_on_submit():
                for event in event_descriptions:
                    await yalc.config.guild(guild).events.set_raw(event, value=getattr(form, event).data)
                return {
                    "status": 0,
                    "notifications": [{"message": "Event settings updated!", "category": "success"}],
                    "redirect_url": kwargs["request_url"],
                }
            html = "<h4>Edit which events are logged:</h4>{{ form|safe }}"
            return {"status": 0, "web_content": {"source": html, "form": form}}
        except Exception as e:
            return {"status": 1, "error_title": "Error", "error_message": str(e)}

    @dashboard_page(
        name="channels",
        description="Set log channels for each event.",
        methods=("GET", "POST"),
    )
    async def dashboard_channels(self, guild: typing.Optional[discord.Guild] = None, Form=None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard page to set log channels for events."""
        try:
            if not guild:
                return {"status": 0, "web_content": {"source": "<h4>No guild selected.</h4>"}}
            yalc = self.bot.get_cog("YALC")
            event_descriptions = getattr(yalc, "event_descriptions", {})
            config = await yalc.config.guild(guild).all()
            event_channels = config.get("event_channels", {})
            text_channels = [(str(c.id), f"#{c.name}") for c in guild.text_channels]
            class ChannelsForm(Form):
                pass
            for event, (_, desc) in event_descriptions.items():
                setattr(
                    ChannelsForm,
                    event,
                    wtforms.SelectField(
                        desc + " Channel",
                        choices=[("", "(None)")] + text_channels,
                        default=str(event_channels.get(event, "")),
                    ),
                )
            setattr(ChannelsForm, "submit", wtforms.SubmitField("Save Changes"))
            form = ChannelsForm()
            if form.validate_on_submit():
                for event in event_descriptions:
                    val = getattr(form, event).data
                    if val:
                        await yalc.config.guild(guild).event_channels.set_raw(event, value=int(val))
                    else:
                        await yalc.config.guild(guild).event_channels.clear_raw(event)
                return {
                    "status": 0,
                    "notifications": [{"message": "Log channels updated!", "category": "success"}],
                    "redirect_url": kwargs["request_url"],
                }
            html = "<h4>Set log channels for each event:</h4>{{ form|safe }}"
            return {"status": 0, "web_content": {"source": html, "form": form}}
        except Exception as e:
            return {"status": 1, "error_title": "Error", "error_message": str(e)}

    @dashboard_page(
        name="tupperbox",
        description="Tupperbox ignore settings.",
        methods=("GET", "POST"),
    )
    async def dashboard_tupperbox(self, guild: typing.Optional[discord.Guild] = None, Form=None, **kwargs) -> typing.Dict[str, typing.Any]:
        """Dashboard page to manage Tupperbox ignore and bot IDs."""
        try:
            if not guild:
                return {"status": 0, "web_content": {"source": "<h4>No guild selected.</h4>"}}
            yalc = self.bot.get_cog("YALC")
            config = await yalc.config.guild(guild).all()
            ignore_tupperbox = config.get("ignore_tupperbox", True)
            tupperbox_ids = config.get("tupperbox_ids", getattr(yalc, "tupperbox_default_ids", []))
            class TupperboxForm(Form):
                ignore = wtforms.BooleanField("Ignore Tupperbox proxy messages", default=ignore_tupperbox)
                ids = wtforms.StringField("Tupperbox Bot IDs (comma separated)", default=", ".join(tupperbox_ids))
                submit = wtforms.SubmitField("Save Changes")
            form = TupperboxForm()
            if form.validate_on_submit():
                await yalc.config.guild(guild).ignore_tupperbox.set(form.ignore.data)
                # Validate IDs: must be 17+ digit numbers, comma separated
                ids = [i.strip() for i in form.ids.data.split(",") if i.strip().isdigit() and len(i.strip()) >= 17]
                await yalc.config.guild(guild).tupperbox_ids.set(ids)
                return {
                    "status": 0,
                    "notifications": [{"message": "Tupperbox settings updated!", "category": "success"}],
                    "redirect_url": kwargs["request_url"],
                }
            html = "<h4>Tupperbox Ignore Settings:</h4>{{ form|safe }}"
            return {"status": 0, "web_content": {"source": html, "form": form}}
        except Exception as e:
            return {"status": 1, "error_title": "Error", "error_message": str(e)}
