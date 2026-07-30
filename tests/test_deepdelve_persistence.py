"""Regression coverage for owner-bound persistent DeepDelve controls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from discord.ui.view import ViewStore

from deepdelve.deepdelve import (
    ActivitiesView,
    AdventureView,
    AtlasView,
    CampaignContinueView,
    CampaignView,
    ChoiceView,
    ClassSelectView,
    CombatView,
    CommissionsView,
    CompanionView,
    CraftView,
    DeepDelve,
    GameHubView,
    InventoryView,
    OriginView,
    ProfessionView,
    PuzzleView,
    QuestJournalView,
    RetireConfirmView,
    SagaView,
    SeasonArchiveView,
    TownView,
)
from deepdelve.persistent_views import (
    BUTTON_TEMPLATE,
    SELECT_TEMPLATE,
    DeepDelveDynamicButton,
    DeepDelveDynamicSelect,
)


def _views() -> list:
    owner = 123456789
    cog = object()
    return [
        AdventureView(cog, owner),
        GameHubView(cog, owner),
        ActivitiesView(cog, owner),
        ProfessionView(cog, owner, {"profession": {"key": ""}}),
        CompanionView(cog, owner, {"companions": {}, "active_companion": ""}),
        CommissionsView(cog, owner, {"profession": {"key": ""}, "commissions": {}}),
        QuestJournalView(
            cog,
            owner,
            {
                "deepest_floor": 0,
                "living_campaign": {"act": 0, "completed": []},
                "quests_v2": {"active": {}, "completed": [], "failed": [], "counters": {}},
                "legacy": {"faction_reputation": {}, "consequence_flags": []},
            },
        ),
        AtlasView(
            cog,
            owner,
            {
                "deepest_floor": 1,
                "atlas": {
                    "discovered": [],
                    "completed": [],
                    "shortcuts": [],
                    "active_dungeon": {},
                    "clues": {},
                },
            },
        ),
        SagaView(
            cog,
            owner,
            {
                "deepest_floor": 1,
                "living_campaign": {
                    "act": 0,
                    "scene": 0,
                    "decision": 0,
                    "choices": {},
                    "completed": [],
                    "ending": "",
                },
            },
        ),
        SeasonArchiveView(
            cog,
            owner,
            {
                "deepest_floor": 1,
                "season_archive": [],
                "season_story": {"active": "", "scene": 0},
            },
        ),
        ClassSelectView(cog, owner),
        OriginView(cog, owner, {"class_key": "vanguard"}),
        TownView(cog, owner),
        ChoiceView(cog, owner, {"options": (("force", "Force It", "⚔️"),)}),
        PuzzleView(cog, owner, {"options": {"answer": "Answer"}}),
        CampaignView(cog, owner, {"power": ("Take Power", "Consequence")}),
        CampaignContinueView(cog, owner),
        CraftView(cog, owner),
        CombatView(
            cog,
            owner,
            {
                "class_key": "vanguard",
                "level": 1,
                "skill_cooldowns": {},
                "consumables": {"lantern_tonic": 1},
            },
        ),
        InventoryView(cog, owner, {"inventory": []}),
        RetireConfirmView(cog, owner),
    ]


def test_player_views_are_persistent_and_owner_bound() -> None:
    async def check() -> None:
        for view in _views():
            assert view.timeout is None
            assert view.is_persistent()
            assert not view.is_finished()
            for item in view.children:
                assert ":123456789:" in item.custom_id
                assert len(item.custom_id) <= 100
                assert isinstance(item, (DeepDelveDynamicButton, DeepDelveDynamicSelect))

    asyncio.run(check())


def test_fully_dynamic_views_register_no_competing_live_callbacks() -> None:
    async def check() -> None:
        store = ViewStore(SimpleNamespace())
        view = AdventureView(object(), 123456789)
        store.add_view(view, message_id=42)
        assert store._views[42] == {}
        assert DeepDelveDynamicButton.__discord_ui_compiled_template__ in store._dynamic_items

    asyncio.run(check())


def test_dynamic_component_templates_reconstruct_routes() -> None:
    async def check() -> None:
        for view in _views():
            for item in view.children:
                template = BUTTON_TEMPLATE if item.custom_id.startswith("deepdelve:b:") else SELECT_TEMPLATE
                match = template.fullmatch(item.custom_id)
                assert match is not None
                dynamic_type = DeepDelveDynamicButton if item.custom_id.startswith("deepdelve:b:") else DeepDelveDynamicSelect
                rebuilt = await dynamic_type.from_custom_id(None, item.item, match)
                assert rebuilt.user_id == 123456789
                assert rebuilt.route == match["route"]

    asyncio.run(check())


def test_dynamic_router_is_the_single_handler_for_player_messages() -> None:
    async def check() -> None:
        dispatch = AsyncMock()
        cog = SimpleNamespace(_dispatch_persistent_button=dispatch)
        interaction = SimpleNamespace(
            response=SimpleNamespace(is_done=lambda: False),
            client=SimpleNamespace(
                get_cog=lambda _name: cog,
            ),
        )
        item = next(iter(_views()[0].children))
        dynamic = DeepDelveDynamicButton(item.item, 123456789, "adventure:explore")
        await dynamic.callback(interaction)
        dispatch.assert_awaited_once_with(interaction, "adventure:explore")

    asyncio.run(check())


def test_adventure_view_has_a_direct_game_hub_route() -> None:
    view = AdventureView(object(), 123456789)
    game_hub = next(item for item in view.children if item.label == "Game Hub")
    assert game_hub.custom_id == "deepdelve:b:123456789:adventure:game_hub"


def test_persistent_adventure_game_hub_route_opens_the_hub() -> None:
    async def check() -> None:
        cog = object.__new__(DeepDelve)
        cog._hub_interaction = AsyncMock()
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=123456789),
        )
        await cog._dispatch_persistent_button(interaction, "adventure:game_hub")
        cog._hub_interaction.assert_awaited_once_with(interaction, "hub")

    asyncio.run(check())


def test_inventory_selection_is_encoded_into_stateless_action_routes() -> None:
    async def check() -> None:
        view = InventoryView(
            object(),
            123456789,
            {
                "inventory": [
                    {
                        "id": "abc123",
                        "name": "Test Blade",
                        "rarity_index": 0,
                        "attack": 2,
                    },
                ],
            },
        )
        view.bind_selection("abc123")
        action_ids = [
            item.custom_id
            for item in view.children
            if getattr(item, "custom_id", "").startswith("deepdelve:b:123456789:inventory:")
            and not item.custom_id.endswith(":back")
        ]
        assert action_ids
        assert all(custom_id.endswith(":abc123") for custom_id in action_ids)
        assert any(":inventory:identify:abc123" in custom_id for custom_id in action_ids)

    asyncio.run(check())


def test_cog_load_purges_legacy_message_bound_player_views() -> None:
    player_view = object()
    world_view = object()
    buckets = {
        1: {
            (2, "player"): SimpleNamespace(
                custom_id="deepdelve:b:123:adventure:explore",
                view=player_view,
            ),
            (2, "world"): SimpleNamespace(
                custom_id="deepdelve:worldboss:strike",
                view=world_view,
            ),
        },
    }
    removed = []
    bot = SimpleNamespace(
        _connection=SimpleNamespace(_view_store=SimpleNamespace(_views=buckets)),
        remove_view=removed.append,
    )
    DeepDelve._purge_live_player_views(SimpleNamespace(bot=bot))
    assert removed == [player_view]


def test_raw_config_merge_accepts_items_under_none_equipment_defaults() -> None:
    defaults = {
        "created": False,
        "equipment": {"weapon": None, "armor": None, "charm": None},
    }
    stored = {
        "created": True,
        "equipment": {
            "weapon": {
                "id": "origin",
                "name": "Watchman's Spear",
                "slot": "weapon",
            },
        },
    }
    merged = DeepDelve._safe_config_merge(defaults, stored)
    assert merged["created"] is True
    assert merged["equipment"]["weapon"]["name"] == "Watchman's Spear"
    assert merged["equipment"]["armor"] is None
    assert defaults["equipment"]["weapon"] is None


def test_hub_acknowledges_before_loading_or_rendering_state() -> None:
    async def check() -> None:
        events = []
        cog = object.__new__(DeepDelve)

        async def get_profile(_guild_id, _user_id):
            events.append("load")
            return {"created": True}

        async def defer():
            events.append("defer")

        async def edit_original_response(**_kwargs):
            events.append("edit")

        cog._get_profile = get_profile
        cog._game_hub_embed = lambda _profile: SimpleNamespace()
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=2),
            response=SimpleNamespace(defer=defer),
            edit_original_response=edit_original_response,
        )
        await cog._hub_interaction(interaction, "hub")
        assert events == ["defer", "load", "edit"]

    asyncio.run(check())
