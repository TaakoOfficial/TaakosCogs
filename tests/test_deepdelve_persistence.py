"""Regression coverage for owner-bound persistent DeepDelve controls."""

from __future__ import annotations

import asyncio

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
