from redbot.core import commands
from redbot.core.bot import Red
import discord
import typing

# Dashboard page decorator for Red-Web-Dashboard third-party integration
def dashboard_page(*args, **kwargs):
    def decorator(func: typing.Callable):
        func.__dashboard_decorator_params__ = (args, kwargs)
        return func
    return decorator

class DashboardIntegration:
    bot: Red

    @commands.Cog.listener()
    async def on_dashboard_cog_add(self, dashboard_cog: commands.Cog) -> None:
        # Register this cog as a third party with the Dashboard
        dashboard_cog.rpc.third_parties_handler.add_third_party(self)

    @dashboard_page(
        name=None,
        description="YALC Dashboard: Manage and view YALC features.",
        methods=("GET", "POST"),
        is_owner=True
    )
    async def yalcdash_main(self, user: discord.User, **kwargs) -> typing.Dict[str, typing.Any]:
        import wtforms

        class YALCForm(kwargs["Form"]):
            def __init__(self):
                super().__init__(prefix="yalc_dashboard_form_")
            action: wtforms.SelectField = wtforms.SelectField(
                "Action:",
                choices=[("view", "View Info"), ("update", "Update Settings")],
                validators=[wtforms.validators.InputRequired()]
            )
            message: wtforms.TextAreaField = wtforms.TextAreaField(
                "Message:",
                validators=[wtforms.validators.Optional(), wtforms.validators.Length(max=2000)],
                default=""
            )
            submit: wtforms.SubmitField = wtforms.SubmitField("Submit")

        form: YALCForm = YALCForm()
        notifications = []

        if form.validate_on_submit():
            action = form.action.data
            msg = form.message.data
            if action == "view":
                notifications.append({"message": "Viewing YALC info.", "category": "info"})
            elif action == "update":
                notifications.append({"message": f"Updated settings: {msg}", "category": "success"})
            else:
                notifications.append({"message": "Unknown action.", "category": "error"})
            return {
                "status": 0,
                "notifications": notifications,
                "redirect_url": kwargs["request_url"],
            }

        source = "{{ form|safe }}"

        return {
            "status": 0,
            "web_content": {"source": source, "form": form},
        }

    @dashboard_page(
        name="guild",
        description="YALC Guild Dashboard: View guild details.",
        methods=("GET",),
    )
    async def yalcdash_guild(self, user: discord.User, guild: discord.Guild, **kwargs) -> typing.Dict[str, typing.Any]:
        return {
            "status": 0,
            "web_content": {
                "source": '<h4>YALC Dashboard: Guild "{{ guild.name }}" ({{ guild.id }})</h4>',
                "guild": guild,
            },
        }