"""DeepDelve 5.0 Living World release-gate coverage."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from deepdelve.art import combat_art_path
from deepdelve.living_content import FACTION_QUESTS, TENETS
from deepdelve.systems.atlas import (
    advance_dungeon,
    enter_dungeon,
    record_dungeon_victory,
    resolve_dungeon_choice,
)
from deepdelve.systems.commissions import accept_commission, commission_board, progress_commission
from deepdelve.systems.content_registry import CONTENT_MINIMUMS, content_counts, reward_budget, validate_content
from deepdelve.systems.economy import economy_release_gate, equivalent_rewards
from deepdelve.systems.legacy import (
    accept_oath,
    equip_tenets,
    grant_resolve,
    oath_board,
    progress_oath,
    unlock_tenet,
)
from deepdelve.systems.living_campaign import ENDINGS, advance_living_campaign, living_campaign_view
from deepdelve.systems.migrations import GUILD_SCHEMA_VERSION, PROFILE_SCHEMA_VERSION, migrate_guild, migrate_profile
from deepdelve.systems.morality import use_moral_power
from deepdelve.systems.nemesis import create_nemesis, defeat_nemesis
from deepdelve.systems.quests import QUESTS, accept_quest, available_quests, expire_quests, progress_quests, resolve_quest
from deepdelve.systems.relationships import give_gift
from deepdelve.systems.sanctum import sanctum_upgrade_cost, upgrade_sanctum
from deepdelve.systems.season_archive import advance_season_chapter, begin_season_chapter


def profile() -> dict:
    return {
        "created": True,
        "created_at": "2026-01-01",
        "alignment": "Pragmatic",
        "morality": 0,
        "convictions": {"mercy": 0, "honesty": 0, "ambition": 0, "ruthlessness": 0},
        "moral_deeds": [],
        "deed_counts": {},
        "floor": 30,
        "deepest_floor": 40,
        "turns": 100,
        "gold": 10_000,
        "xp": 0,
        "level": 20,
        "potions": 0,
        "arcane_shards": 0,
        "materials": {"iron": 5, "silk": 5, "ember": 5, "essence": 5, "voidglass": 5},
        "profession": {"key": "blacksmith", "level": 10, "xp": 0},
        "profession_mastery": {},
        "profession_mastery_points": 100,
        "recipes": [],
        "active_rumor": {},
        "npc_reputation": {},
    }


def test_release_content_meets_every_committed_minimum() -> None:
    counts = content_counts()
    assert not validate_content()
    assert all(counts[key] >= minimum for key, minimum in CONTENT_MINIMUMS.items())


def test_v8_migration_is_idempotent_and_credits_campaign_deeds_once() -> None:
    old = profile()
    old["moral_deeds"] = [
        {"key": "campaign:first:mercy", "name": "First", "morality": 3, "convictions": {}},
        {"key": "event:repeat:aid", "name": "Repeat", "morality": 3, "convictions": {}},
    ]
    assert migrate_profile(old)
    assert old["schema_version"] == PROFILE_SCHEMA_VERSION == 8
    assert old["legacy"]["resolve"] == 1
    snapshot = old["legacy"].copy()
    assert not migrate_profile(old)
    assert old["legacy"] == snapshot

    guild = {}
    assert migrate_guild(guild)
    assert guild["schema_version"] == GUILD_SCHEMA_VERSION == 6
    assert not migrate_guild(guild)


def test_every_prior_schema_fixture_migrates_idempotently() -> None:
    for version in range(PROFILE_SCHEMA_VERSION):
        old = profile()
        old["schema_version"] = version
        assert migrate_profile(old)
        assert old["schema_version"] == PROFILE_SCHEMA_VERSION
        assert not migrate_profile(old)
        assert set(old["legacy"]["faction_reputation"]) == {"lantern", "concord", "court"}
        assert len(old["sanctum"]["rooms"]) == 5
    for version in range(GUILD_SCHEMA_VERSION):
        old_guild = {"schema_version": version}
        assert migrate_guild(old_guild)
        assert old_guild["schema_version"] == GUILD_SCHEMA_VERSION
        assert not migrate_guild(old_guild)


def test_resolve_is_unique_and_tenets_are_capped_to_three() -> None:
    data = profile()
    data["morality"] = 70
    assert grant_resolve(data, 8, "unique") == 8
    assert grant_resolve(data, 8, "unique") == 0
    radiant = [key for key, definition in TENETS.items() if definition["path"] == "radiant"]
    for key in radiant[:4]:
        assert unlock_tenet(data, key)[0]
    assert equip_tenets(data, radiant[:3])[0]
    assert not equip_tenets(data, radiant[:4])[0]


def test_oath_routes_have_equal_value_and_claim_once() -> None:
    data = profile()
    board = oath_board(data, date(2026, 7, 28))
    assert len(board) == 3
    assert len({(entry["reward"]["gold"], entry["reward"]["xp"], entry["reward"]["faction_reputation"]) for entry in board}) == 1
    chosen = board[0]
    assert accept_oath(data, chosen["faction"], date(2026, 7, 28))[0]
    for _ in range(chosen["target"]):
        lines = progress_oath(data, chosen["objective"])
    gold_after = data["gold"]
    assert any("fulfilled" in line for line in lines)
    assert not progress_oath(data, chosen["objective"])
    assert data["gold"] == gold_after


def test_quest_claim_is_idempotent_and_outcome_rewards_are_equal() -> None:
    data = profile()
    key = next(iter(FACTION_QUESTS["lantern"]))["key"]
    assert accept_quest(data, key)[0]
    objective = FACTION_QUESTS["lantern"][0]["objective"]
    progress_quests(data, objective, 99)
    before = data["gold"]
    assert resolve_quest(data, key, "mercy")[0]
    assert data["gold"] > before
    after = data["gold"]
    assert not resolve_quest(data, key, "mercy")[0]
    assert data["gold"] == after
    budgets = {
        outcome: reward_budget(FACTION_QUESTS["lantern"][0]["reward"])
        for outcome in ("mercy", "honesty", "ambition", "ruthlessness")
    }
    assert max(budgets.values()) == min(budgets.values())


def test_journal_has_every_category_prerequisites_and_timed_failure() -> None:
    data = profile()
    assert {quest["category"] for quest in available_quests(data)} == {
        "main",
        "faction",
        "character",
        "side",
        "bounty",
        "profession",
        "moral",
        "seasonal",
    }
    second_faction = FACTION_QUESTS["lantern"][1]["key"]
    assert not accept_quest(data, second_faction)[0]
    bounty_key = next(key for key, quest in QUESTS.items() if quest["category"] == "bounty")
    assert accept_quest(data, bounty_key)[0]
    data["quests_v2"]["active"][bounty_key]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    assert expire_quests(data)
    assert bounty_key in data["quests_v2"]["failed"]
    assert bounty_key not in data["quests_v2"]["active"]


def test_named_dungeon_spends_declared_energy_and_saves_checkpoints() -> None:
    data = profile()
    assert enter_dungeon(data, "ossuary_of_rain")[0]
    start = data["turns"]
    assert advance_dungeon(data)[0]  # authored moral room
    assert resolve_dungeon_choice(data, "honesty")[0]
    assert advance_dungeon(data)[0]  # tactical enemy
    enemy = data["encounter"]
    assert enemy["atlas_room"] == 2
    assert enemy["art_name"] != enemy["name"]
    assert combat_art_path(enemy) is not None
    assert record_dungeon_victory(data, enemy)
    data["encounter"] = {}
    assert advance_dungeon(data)[0]  # records victory without energy
    assert advance_dungeon(data)[0]  # checkpoint puzzle
    pending = data["atlas"]["active_dungeon"]["pending"]
    assert resolve_dungeon_choice(data, pending["options"][0])[0]
    assert data["turns"] == start - 3
    assert data["atlas"]["active_dungeon"]["checkpoint"] == 3


def test_named_dungeon_requires_authored_choices_and_boss_victory_to_complete() -> None:
    data = profile()
    assert enter_dungeon(data, "lanternless_hospice")[0]
    start = data["turns"]
    guard = 0
    while data["atlas"]["active_dungeon"]:
        guard += 1
        assert guard < 30
        run = data["atlas"]["active_dungeon"]
        if run.get("pending"):
            assert resolve_dungeon_choice(data, run["pending"]["options"][0])[0]
        elif data.get("encounter"):
            enemy = data["encounter"]
            assert record_dungeon_victory(data, enemy)
            data["encounter"] = {}
        else:
            assert advance_dungeon(data)[0]
    assert data["turns"] == start - 7
    assert "lanternless_hospice" in data["atlas"]["completed"]
    assert any(flag.startswith("dungeon:lanternless_hospice") for flag in data["legacy"]["consequence_flags"])


def test_six_act_campaign_has_36_paid_scenes_18_decisions_and_an_ending() -> None:
    data = profile()
    choices = ("mercy", "honesty", "ambition", "ruthlessness")
    start = data["turns"]
    decision_index = 0
    guard = 0
    while not living_campaign_view(data)["complete"]:
        guard += 1
        assert guard < 100
        view = living_campaign_view(data)
        result = advance_living_campaign(data, choices[decision_index % 4] if view["needs_choice"] else None)
        assert result["ok"]
        if view["needs_choice"]:
            decision_index += 1
    state = data["living_campaign"]
    assert data["turns"] == start - 36
    assert len(state["choices"]) == 18
    assert len(state["completed"]) == 6
    assert state["ending"] in ENDINGS


def test_season_chapters_are_permanent_and_cost_eight_energy() -> None:
    data = profile()
    start = data["turns"]
    assert begin_season_chapter(data, 1)[0]
    for _ in range(3):
        assert advance_season_chapter(data)[0]
    assert data["turns"] == start - 8
    assert data["season_archive"] == ["season_chapter_1"]
    assert not begin_season_chapter(data, 1)[0]


def test_sanctum_is_a_capped_sink_with_no_resale_path() -> None:
    data = profile()
    costs = []
    for _ in range(3):
        costs.append(sanctum_upgrade_cost(data, "hall"))
        assert upgrade_sanctum(data, "hall")[0]
    assert not upgrade_sanctum(data, "hall")[0]
    assert data["sanctum"]["spent"] == sum(costs)
    assert data["gold"] == 10_000 - sum(costs)


def test_nemesis_slots_cap_and_trophies_are_bound() -> None:
    data = profile()
    enemy = {"name": "Test Horror"}
    for _ in range(5):
        create_nemesis(data, enemy, force=True)
    assert len(data["nemeses"]["active"]) == 3
    nemesis_id = data["nemeses"]["active"][0]["id"]
    assert defeat_nemesis(data, nemesis_id)[0]
    assert data["nemeses"]["defeated"][0]["bound"]


def test_gifts_consume_materials_and_are_daily_capped() -> None:
    data = profile()
    assert give_gift(data, "orra", "iron")[0]
    assert data["materials"]["iron"] == 4
    assert not give_gift(data, "orra", "iron")[0]


def test_weekly_commission_rewards_exactly_once() -> None:
    data = profile()
    offers = commission_board(data)
    assert len(offers) == 3
    assert accept_commission(data, 1)[0]
    active = data["commissions"]["active"]
    for _ in range(active["target"]):
        lines = progress_commission(data, active["objective"])
    gold_after = data["gold"]
    assert any("complete" in line for line in lines)
    assert not progress_commission(data, active["objective"])
    assert data["gold"] == gold_after


def test_conviction_scaling_caps_after_threshold() -> None:
    stats = {"max_hp": 100, "max_mana": 20, "attack": 20}
    enemy_low = {"hp": 100, "defense": 5}
    enemy_high = {"hp": 100, "defense": 5}
    low = profile()
    high = profile()
    for data, score in ((low, -70), (high, -70)):
        data.update({"morality": score, "hp": 50, "mana": 0, "status": {}, "combat_flags": {}})
    low["convictions"]["ruthlessness"] = 25
    low["convictions"]["ambition"] = 25
    high["convictions"]["ruthlessness"] = 100
    high["convictions"]["ambition"] = 100
    assert use_moral_power(low, enemy_low, stats)["ok"]
    assert use_moral_power(high, enemy_high, stats)["ok"]
    assert enemy_low["hp"] == enemy_high["hp"]
    assert low["hp"] == high["hp"]


def test_main_campaign_cannot_pay_twice_through_journal() -> None:
    data = profile()
    ok, message = accept_quest(data, "main:living_act_1")
    assert not ok
    assert "cannot be claimed twice" in message


def test_reward_routes_and_long_horizon_economy_are_fair() -> None:
    assert equivalent_rewards(
        [
            {"gold": 100, "xp": 100, "materials": 1},
            {"gold": 93, "xp": 110, "materials": 1},
            {"gold": 105, "xp": 95, "materials": 1},
        ],
    )
    projections = economy_release_gate()
    assert set(projections) == {7, 30, 90}
    assert all(result["within_target"] for result in projections.values())
    assert all(result["saved"] >= 0 for result in projections.values())
