"""Regression coverage for owner-bound persistent DeepDelve controls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from deepdelve.deepdelve import (
    AdventureView,
    CampaignContinueView,
    CampaignView,
    ChoiceView,
    ClassSelectView,
    CombatView,
    CraftView,
    InventoryView,
    OriginView,
    PuzzleView,
    RetireConfirmView,
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
            for item in view.children:
                assert ":123456789:" in item.custom_id
                assert len(item.custom_id) <= 100

    asyncio.run(check())


def test_dynamic_component_templates_reconstruct_routes() -> None:
    async def check() -> None:
        for view in _views():
            for item in view.children:
                template = BUTTON_TEMPLATE if item.custom_id.startswith("deepdelve:b:") else SELECT_TEMPLATE
                match = template.fullmatch(item.custom_id)
                assert match is not None
                dynamic_type = DeepDelveDynamicButton if item.custom_id.startswith("deepdelve:b:") else DeepDelveDynamicSelect
                rebuilt = await dynamic_type.from_custom_id(None, item, match)
                assert rebuilt.user_id == 123456789
                assert rebuilt.route == match["route"]

    asyncio.run(check())


def test_dynamic_recovery_yields_to_the_exact_registered_live_view() -> None:
    async def check() -> None:
        dispatch = AsyncMock()
        cog = SimpleNamespace(_dispatch_persistent_button=dispatch)
        custom_id = "deepdelve:b:123456789:adventure:explore"
        live_items = {(2, custom_id): object()}
        interaction = SimpleNamespace(
            response=SimpleNamespace(is_done=lambda: True),
            client=SimpleNamespace(
                get_cog=lambda _name: cog,
                _connection=SimpleNamespace(
                    _view_store=SimpleNamespace(_views={42: live_items}),
                ),
            ),
            message=SimpleNamespace(id=42, interaction_metadata=None),
            data={"component_type": 2, "custom_id": custom_id},
        )
        item = next(iter(_views()[0].children))
        dynamic = DeepDelveDynamicButton(item, 123456789, "adventure:explore")
        await dynamic.callback(interaction)
        dispatch.assert_not_awaited()

    asyncio.run(check())


def test_dynamic_recovery_dispatches_an_orphaned_message_after_handoff() -> None:
    async def check() -> None:
        dispatch = AsyncMock()
        cog = SimpleNamespace(_dispatch_persistent_button=dispatch)
        interaction = SimpleNamespace(
            response=SimpleNamespace(is_done=lambda: False),
            client=SimpleNamespace(
                get_cog=lambda _name: cog,
                _connection=SimpleNamespace(
                    _view_store=SimpleNamespace(_views={}),
                ),
            ),
            message=SimpleNamespace(id=42, interaction_metadata=None),
            data={
                "component_type": 2,
                "custom_id": "deepdelve:b:123456789:adventure:explore",
            },
        )
        item = next(iter(_views()[0].children))
        dynamic = DeepDelveDynamicButton(item, 123456789, "adventure:explore")
        await dynamic.callback(interaction)
        dispatch.assert_awaited_once_with(interaction, "adventure:explore")

    asyncio.run(check())
