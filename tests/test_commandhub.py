"""Focused tests for CommandHub's runtime-independent contracts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from redbot.core import app_commands, commands

from commandhub.commandhub import CommandHub
from commandhub.config import migrate_payload
from commandhub.converters import ConversionError, convert_argument, extract_id
from commandhub.integrations.slashlink import SlashLinkAdapter
from commandhub.models import (
    CommandAssignment,
    CommandParameter,
    CommandSource,
    Hub,
    HubCategory,
    HubCommand,
    ParameterKind,
    RepeatRecord,
)
from commandhub.registry import CommandRegistry, normalize_application, normalize_prefix
from commandhub.suggestions import (
    CogMetadata,
    build_bootstrap_plan,
    build_suggestion_plan,
    classify_command,
    read_loaded_cog_metadata,
)
from commandhub.utils import (
    Debouncer,
    ValidationError,
    hub_scope_allows,
    is_potentially_destructive,
    paginate,
    rank_commands,
    validate_hub_name,
)


class CustomTransformer(app_commands.Transformer):
    async def transform(self, interaction, value: str) -> str:
        return value


def test_hub_name_validation() -> None:
    assert validate_hub_name("games-2") == "games-2"
    for invalid in ("Games", "has space", "", "x" * 33, "é"):
        try:
            validate_hub_name(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"{invalid!r} should be invalid")


def test_config_migration_preserves_commands_and_adds_v2_fields() -> None:
    payload = {
        "hubs": {
            "games": {
                "categories": {"General": {"commands": [{"qualified_name": "trivia start", "source": "prefix"}]}},
                "required_permissions": ["manage_guild"],
            },
        },
    }
    migrated = migrate_payload(payload, 1)
    hub = migrated["hubs"]["games"]
    assert hub["name"] == "games"
    assert hub["required_user_permissions"] != 0
    assert hub["categories"]["General"]["commands"][0]["disabled"] is False
    assert "sync_debounce_seconds" in migrated["settings"]


def _hub_command(
    name: str,
    description: str = "",
    *,
    category: str | None = None,
    cog: str = "Example",
    permissions: int = 0,
    enabled: bool = True,
    unsupported: str | None = None,
) -> HubCommand:
    return HubCommand(
        CommandSource.PREFIX,
        name,
        name,
        description,
        cog,
        category,
        required_user_permissions=permissions,
        enabled=enabled,
        unsupported_reason=unsupported,
    )


def test_search_ranking_exact_prefix_then_description() -> None:
    commands_ = [
        _hub_command("show balance", "economy balance details"),
        _hub_command("balance history"),
        _hub_command("balance"),
    ]
    assert [item.qualified_name for item in rank_commands(commands_, "balance")] == [
        "balance",
        "balance history",
        "show balance",
    ]


def test_bootstrap_plan_groups_selected_cogs_and_reports_only_their_skips() -> None:
    commands_ = [
        _hub_command("roleinfo", cog="Toolz"),
        _hub_command("roleaudit", cog="Toolz", unsupported="custom converter"),
        _hub_command("role delete", cog="RoleKit"),
        _hub_command("weather", cog="Weather", unsupported="attachment input"),
    ]
    plan = build_bootstrap_plan(commands_, "utility", ["toolz", "RoleKit"])
    assert list(plan.hubs["utility"].categories) == ["RoleKit", "Toolz"]
    assert plan.command_count == 2
    assert plan.skipped == ["roleaudit: custom converter"]
    assert plan.hubs["utility"].categories["RoleKit"][0].confirmation_required is True


def test_suggestion_plan_uses_permissions_keywords_and_safe_fallback() -> None:
    commands_ = [
        _hub_command("roleaudit", cog="Toolz", permissions=1),
        _hub_command("roleinfo", cog="Toolz"),
        _hub_command("wheel spin", cog="SpinWheel"),
        _hub_command("ticket open", cog="TicketHub"),
        _hub_command("hello", cog="Greeter"),
        _hub_command("suggest", cog="CommandHub"),
        _hub_command("broken", cog="Example", unsupported="unsupported transform"),
    ]
    plan = build_suggestion_plan(commands_)
    assert set(plan.hubs) == {"admin", "community", "fun", "other", "utility"}
    assert classify_command(commands_[0]) == "admin"
    assert classify_command(commands_[1]) == "utility"
    assert plan.command_count == 5
    assert plan.skipped == ["broken: unsupported transform"]


def test_loaded_cog_metadata_keeps_runtime_name_alias() -> None:
    class ExampleCog:
        qualified_name = "RuntimeCog"
        description = "Runtime description"

    metadata = asyncio.run(read_loaded_cog_metadata([ExampleCog()]))
    assert metadata["runtimecog"].description == "Runtime description"


def test_cog_metadata_can_drive_a_suggestion() -> None:
    command = _hub_command("hello", cog="Radio")
    assert classify_command(command, CogMetadata("Radio", tags=("music",))) == "music"


def test_apply_plan_creates_categories_and_skips_existing_assignments() -> None:
    command = _hub_command("role delete", cog="RoleKit")
    plan = build_bootstrap_plan([command], "utility", ["RoleKit"])

    class Store:
        def __init__(self) -> None:
            self.hubs: dict[str, Hub] = {}

        async def get_hub(self, guild_id: int, name: str) -> Hub | None:
            return self.hubs.get(name.casefold())

        async def save_hub(self, guild_id: int, hub: Hub) -> None:
            self.hubs[hub.name.casefold()] = hub

    async def scenario() -> None:
        cog = object.__new__(CommandHub)
        cog.store = Store()
        cog.registry = SimpleNamespace(
            get=lambda source, qualified_name: (
                command if (source, qualified_name) == (command.source, command.qualified_name) else None
            ),
        )
        cog._tree_name_conflict = lambda guild_id, name: False
        sync_calls = 0

        async def record_sync(guild_id: int) -> None:
            nonlocal sync_calls
            sync_calls += 1

        cog._reconcile_tree = record_sync
        cog.schedule_sync = record_sync

        result = await cog.apply_suggestion_plan_service(1, plan)
        hub = cog.store.hubs["utility"]
        assert list(hub.categories) == ["RoleKit"]
        assert hub.categories["RoleKit"].commands[0].confirmation_required is True
        assert result == {"commands_added": 1, "duplicates": 0, "hubs_changed": 1}
        assert sync_calls == 2

        repeated = await cog.apply_suggestion_plan_service(1, plan)
        assert repeated == {"commands_added": 0, "duplicates": 1, "hubs_changed": 0}

    asyncio.run(scenario())


def test_pagination_clamps_and_obeys_component_limit() -> None:
    page, current, pages = paginate(list(range(60)), 99)
    assert page == list(range(50, 60))
    assert (current, pages) == (2, 3)


def test_permission_filtering_honors_allow_block_and_bitfields() -> None:
    hub = Hub.create("admin")
    hub.allowed_roles = [10]
    hub.blocked_roles = [20]
    hub.allowed_channels = [30]
    hub.required_user_permissions = 0b010
    hub.required_bot_permissions = 0b100
    assert hub_scope_allows(hub, {10}, 30, 0b011, 0b101) == (True, None)
    assert hub_scope_allows(hub, {10, 20}, 30, 0b011, 0b101)[0] is False
    assert hub_scope_allows(hub, {10}, 31, 0b011, 0b101)[0] is False
    assert hub_scope_allows(hub, {10}, 30, 0, 0b101)[0] is False


def test_primitive_argument_conversion_and_errors() -> None:
    assert extract_id("123456789012345678") == 123456789012345678
    assert extract_id("<@123456789012345678>") == 123456789012345678
    interaction = SimpleNamespace(guild=None)

    async def scenario() -> None:
        assert await convert_argument(interaction, CommandParameter("count", kind=ParameterKind.INTEGER), "42") == 42
        bounded = CommandParameter("count", kind=ParameterKind.INTEGER, minimum=1, maximum=10)
        try:
            await convert_argument(interaction, bounded, "11")
        except ConversionError:
            pass
        else:
            raise AssertionError("out-of-range integer accepted")
        assert await convert_argument(interaction, CommandParameter("enabled", kind=ParameterKind.BOOLEAN), "yes") is True
        choice = CommandParameter("mode", kind=ParameterKind.CHOICE, choices={"Fast": "fast"})
        assert await convert_argument(interaction, choice, "FAST") == "fast"
        try:
            await convert_argument(interaction, CommandParameter("enabled", kind=ParameterKind.BOOLEAN), "maybe")
        except ConversionError:
            pass
        else:
            raise AssertionError("invalid boolean accepted")

    asyncio.run(scenario())


def test_prefix_normalization_preserves_nested_qualified_name() -> None:
    @commands.group(name="settings")
    async def settings(ctx: commands.Context) -> None:
        pass

    @settings.group(name="notifications")
    async def notifications(ctx: commands.Context) -> None:
        pass

    @notifications.command(name="level")
    @commands.has_permissions(manage_messages=True)
    async def level(ctx: commands.Context, number: int) -> None:
        pass

    normalized = normalize_prefix(level)
    assert normalized.qualified_name == "settings notifications level"
    assert normalized.parameters[0].kind is ParameterKind.INTEGER
    assert normalized.required_user_permissions != 0

    @commands.command()
    async def many(ctx: commands.Context, values: commands.Greedy[int]) -> None:
        pass

    assert "greedy collection" in (normalize_prefix(many).unsupported_reason or "")


def test_application_normalization() -> None:
    @app_commands.command(name="roll", description="Roll dice")
    async def roll(interaction, sides: int) -> None:
        pass

    normalized = normalize_application(roll, ("games", "dice"))
    assert normalized.qualified_name == "games dice roll"
    assert normalized.parameters[0].kind is ParameterKind.INTEGER

    @app_commands.command(name="bounded", description="Bounded value")
    async def bounded(interaction, value: app_commands.Range[int, 1, 10]) -> None:
        pass

    assert normalize_application(bounded).parameters[0].minimum == 1

    @app_commands.command(name="custom", description="Custom transform")
    async def custom(interaction, value: app_commands.Transform[str, CustomTransformer]) -> None:
        pass

    assert normalize_application(custom).unsupported_reason is not None


def test_missing_command_lookup_returns_none() -> None:
    registry = object.__new__(CommandRegistry)
    registry.commands = {}
    assert registry.get(CommandSource.PREFIX, "unloaded command") is None


def test_slashlink_unavailable_and_compatible_adapter() -> None:
    class Bot:
        cog = None

        def get_cog(self, name: str):
            return self.cog

    bot = Bot()
    adapter = SlashLinkAdapter(bot)
    assert adapter.available is False

    class Compatible:
        async def get_linked_commands(self):
            return [SimpleNamespace(qualified_name="linked ping")]

        async def get_command_schema(self, qualified_name):
            return {"name": qualified_name}

        async def invoke_linked_command(self, interaction, qualified_name, arguments):
            return None

    bot.cog = Compatible()
    assert adapter.available is True
    assert asyncio.run(adapter.get_linked_commands())[0].qualified_name == "linked ping"


def test_duplicate_assignment_prevention_contract() -> None:
    hub = Hub.create("games")
    assignment = CommandAssignment("trivia start", CommandSource.PREFIX)
    hub.categories["General"].commands.append(assignment)
    assert hub.find_assignment("TRIVIA START", CommandSource.PREFIX) == ("General", assignment)


def test_sync_debouncer_collapses_repeated_schedules() -> None:
    calls = 0

    async def scenario() -> None:
        nonlocal calls

        async def callback() -> None:
            nonlocal calls
            calls += 1

        debouncer = Debouncer(callback)
        debouncer.schedule(0.01)
        debouncer.schedule(0.01)
        debouncer.schedule(0.01)
        await asyncio.sleep(0.04)

    asyncio.run(scenario())
    assert calls == 1


def test_destructive_confirmation_is_persisted_in_assignment() -> None:
    assert is_potentially_destructive("admin ban") is True
    assert is_potentially_destructive("games trivia") is False
    assignment = CommandAssignment("admin ban", CommandSource.PREFIX, confirmation_required=True)
    restored = CommandAssignment.from_dict(assignment.to_dict())
    assert restored.confirmation_required is True


def test_repeat_serialization_rejects_discord_objects_and_accepts_scalars() -> None:
    safe = RepeatRecord("games", "roll", CommandSource.PREFIX, {"sides": 20}, "now")
    unsafe = RepeatRecord("admin", "ban", CommandSource.PREFIX, {"target": object()}, "now")
    assert CommandHub._repeat_is_serializable(safe) is True
    assert CommandHub._repeat_is_serializable(unsafe) is False


def test_category_and_assignment_round_trip() -> None:
    category = HubCategory("Trivia", 2, [CommandAssignment("trivia start", CommandSource.HYBRID, 1, True)])
    restored = HubCategory.from_dict("Trivia", category.to_dict())
    assert restored.position == 2
    assert restored.commands[0].qualified_name == "trivia start"
    assert restored.commands[0].confirmation_required is True
