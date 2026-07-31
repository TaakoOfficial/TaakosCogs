"""Regression coverage for owner-bound persistent DeepDelve controls."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
    MailView,
    OriginView,
    ProfessionView,
    ProgressionView,
    PuzzleView,
    QuestJournalView,
    RetireConfirmView,
    SagaView,
    SanctumView,
    SeasonArchiveView,
    TownView,
    daily_reset_text,
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
        ProgressionView(
            cog,
            owner,
            {
                "attribute_points": 1,
                "attributes": {"might": 0, "finesse": 0, "insight": 0, "vitality": 0, "fortune": 0},
                "class_key": "vanguard",
                "level": 10,
                "subclass": "",
                "talent_points": 1,
                "talents": {},
                "titles": ["delver"],
                "current_title": "",
            },
        ),
        MailView(cog, owner, {"mailbox": [{"key": "welcome"}], "mail_read": []}),
        SanctumView(
            cog,
            owner,
            {
                "gold": 1000,
                "sanctum": {
                    "rooms": {"hall": 0, "library": 0, "workshop": 0, "garden": 0, "observatory": 0},
                    "spent": 0,
                    "cosmetics": [],
                    "active_cosmetic": "",
                },
            },
        ),
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


def test_persistent_navigation_routes_open_the_expected_parent() -> None:
    async def check() -> None:
        expected_destinations = {
            "adventure:game_hub": "hub",
            "activities:back": "hub",
            "town:game_hub": "hub",
            "inventory:game_hub": "hub",
            "mail:back": "hub",
            "sanctum:back": "hub",
            "questjournal:back": "hub",
            "atlas:back": "hub",
            "profession:back": "activities",
            "progression:back": "hub",
            "companion:back": "activities",
            "commissions:back": "activities",
            "saga:back": "activities",
            "seasonarchive:back": "activities",
        }
        cog = object.__new__(DeepDelve)
        cog._hub_interaction = AsyncMock()
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=123456789),
        )
        for route, destination in expected_destinations.items():
            cog._hub_interaction.reset_mock()
            await cog._dispatch_persistent_button(interaction, route)
            cog._hub_interaction.assert_awaited_once_with(interaction, destination)

    asyncio.run(check())


def test_progression_menu_spends_one_attribute_point_and_refreshes() -> None:
    async def check() -> None:
        profile = {
            "gold": 40,
            "attribute_points": 2,
            "attributes": {"might": 0, "finesse": 0, "insight": 0, "vitality": 0, "fortune": 0},
            "class_key": "vanguard",
            "level": 1,
            "subclass": "",
            "talent_points": 0,
            "talents": {},
            "titles": [],
        }
        cog = object.__new__(DeepDelve)
        cog._lock_for = lambda _guild_id, _user_id: asyncio.Lock()
        cog._get_profile = AsyncMock(return_value=profile)
        cog._save_profile = AsyncMock(return_value=profile)
        cog._progression_embed = lambda _profile: SimpleNamespace(description="Character path")
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=123456789),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        await cog._progression_spend_interaction(interaction, "might")

        assert profile["attribute_points"] == 1
        assert profile["attributes"]["might"] == 1
        cog._save_profile.assert_awaited_once_with(1, 123456789, profile, 40)
        refreshed = interaction.edit_original_response.await_args.kwargs["view"]
        assert isinstance(refreshed, ProgressionView)
        attribute_buttons = [
            item
            for item in refreshed.children
            if str(getattr(item, "label", "")).endswith("+1")
        ]
        assert len(attribute_buttons) == 5
        assert all(not item.disabled for item in attribute_buttons)

    asyncio.run(check())


def test_unfinished_active_quest_can_be_abandoned_from_the_menu() -> None:
    view = QuestJournalView(
        object(),
        123456789,
        {
            "deepest_floor": 0,
            "living_campaign": {"act": 0, "completed": []},
            "quests_v2": {
                "active": {"test_quest": {"progress": 0, "target": 3}},
                "completed": [],
                "failed": [],
                "counters": {},
            },
            "legacy": {"faction_reputation": {}, "consequence_flags": []},
        },
    )
    selector = next(item for item in view.children if isinstance(item, DeepDelveDynamicSelect))
    assert any(option.value == "abandon|test_quest" for option in selector.item.options)


def test_every_rendered_persistent_component_has_a_dispatch_route() -> None:
    async def check() -> None:
        cog = object.__new__(DeepDelve)
        async_handlers = (
            "_archive_menu_interaction",
            "_atlas_menu_interaction",
            "_campaign_interaction",
            "_choice_interaction",
            "_combat_interaction",
            "_commission_select_interaction",
            "_companion_select_interaction",
            "_contract_interaction",
            "_craft_interaction",
            "_handle_explore_interaction",
            "_hub_interaction",
            "_inventory_interaction",
            "_origin_begin",
            "_origin_interaction",
            "_profession_gather_interaction",
            "_profession_select_interaction",
            "_progression_spend_interaction",
            "_progression_subclass_interaction",
            "_progression_talent_interaction",
            "_progression_title_interaction",
            "_puzzle_interaction",
            "_quest_menu_interaction",
            "_saga_menu_interaction",
            "_show_crafting_interaction",
            "_show_inventory_interaction",
            "_mail_mark_read_interaction",
            "_sanctum_upgrade_interaction",
            "_town_interaction",
        )
        for name in async_handlers:
            setattr(cog, name, AsyncMock())
        cog._create_character = AsyncMock(return_value=True)
        cog._get_profile = AsyncMock(return_value={"class_key": "vanguard", "inventory": []})
        cog._persistent_error = AsyncMock()
        cog._adventure_embed = lambda _profile: SimpleNamespace()
        cog._inventory_embed = lambda _profile, _selected=None: SimpleNamespace()
        cog._origin_embed = lambda _profile: SimpleNamespace()
        cog._profile_embed = lambda _user, _profile: SimpleNamespace()
        cog._town_embed = lambda _profile: SimpleNamespace()
        cog.config = SimpleNamespace(
            member_from_ids=lambda _guild_id, _user_id: SimpleNamespace(clear=AsyncMock()),
        )
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=123456789, display_name="Route Tester"),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        for view in _views():
            for item in view.children:
                cog._persistent_error.reset_mock()
                if isinstance(item, DeepDelveDynamicButton):
                    await cog._dispatch_persistent_button(interaction, item.route)
                elif isinstance(item, DeepDelveDynamicSelect):
                    selected = str(item.item.options[0].value)
                    await cog._dispatch_persistent_select(interaction, item.route, [selected])
                else:
                    raise AssertionError(f"Unexpected persistent component: {type(item).__name__}")
                cog._persistent_error.assert_not_awaited()

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
            and not item.custom_id.endswith(":game_hub")
        ]
        assert action_ids
        assert all(custom_id.endswith(":abc123") for custom_id in action_ids)
        assert any(":inventory:identify:abc123" in custom_id for custom_id in action_ids)
        assert any(
            getattr(item, "custom_id", "").endswith(":inventory:game_hub")
            for item in view.children
        )

    asyncio.run(check())


def test_daily_reset_timestamp_uses_next_utc_midnight() -> None:
    now = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)

    assert daily_reset_text(now) == "<t:1767312000:F> (<t:1767312000:R>)"


def test_equipped_items_have_a_separate_inventory_selector() -> None:
    async def check() -> None:
        view = InventoryView(
            object(),
            123456789,
            {
                "inventory": [
                    {
                        "id": f"pack-{index}",
                        "name": f"Pack Item {index}",
                        "rarity_index": 0,
                        "attack": 2,
                    }
                    for index in range(25)
                ],
                "equipment": {
                    "weapon": {
                        "id": "equipped-weapon",
                        "name": "Equipped Blade",
                        "rarity_index": 1,
                        "attack": 5,
                    },
                    "armor": None,
                    "charm": None,
                },
            },
        )

        selectors = [item for item in view.children if isinstance(item, DeepDelveDynamicSelect)]
        assert len(selectors) == 2
        assert len(selectors[0].item.options) == 25
        assert [option.value for option in selectors[1].item.options] == ["equipped-weapon"]
        assert selectors[1].route == "equipped_item_select"

    asyncio.run(check())


def test_inventory_upgrade_can_target_equipped_item() -> None:
    async def check() -> None:
        equipped_weapon = {
            "id": "equipped-weapon",
            "name": "Equipped Blade",
            "slot": "weapon",
            "rarity_index": 0,
            "attack": 5,
            "upgrade": 0,
        }
        profile = {
            "gold": 500,
            "arcane_shards": 20,
            "inventory": [],
            "equipment": {"weapon": equipped_weapon, "armor": None, "charm": None},
            "favorite_items": [],
        }
        cog = object.__new__(DeepDelve)
        cog._lock_for = lambda _guild_id, _user_id: asyncio.Lock()
        cog._get_profile = AsyncMock(return_value=profile)
        cog._save_profile = AsyncMock(return_value=profile)
        cog._inventory_embed = lambda _profile, _selected=None: SimpleNamespace(description="Inventory")
        interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            user=SimpleNamespace(id=123456789),
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock(),
        )

        await cog._inventory_interaction(interaction, "equipped-weapon", "upgrade")

        assert profile["equipment"]["weapon"] is equipped_weapon
        assert equipped_weapon["upgrade"] == 1
        assert equipped_weapon["attack"] == 6
        assert profile["gold"] == 425
        assert profile["arcane_shards"] == 18
        cog._save_profile.assert_awaited_once_with(1, 123456789, profile, 500)
        interaction.followup.send.assert_not_awaited()

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
