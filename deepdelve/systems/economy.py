"""Living World economy budgets and deterministic long-horizon projections."""

from __future__ import annotations

from typing import Any

from deepdelve.systems.sanctum import SANCTUM_ROOMS

TARGET_SINK_RANGE = (0.55, 0.75)


def reward_budget(reward: dict[str, Any]) -> float:
    """Convert a mixed reward into one comparable, documented value score."""
    return round(
        int(reward.get("gold", 0))
        + int(reward.get("xp", 0)) * 0.7
        + int(reward.get("resolve", 0)) * 100
        + int(reward.get("faction_reputation", 0)) * 20
        + int(reward.get("relationship", 0)) * 20
        + int(reward.get("materials", 0)) * 18
        + int(reward.get("rarity", 0)) * 45,
        2,
    )


def equivalent_rewards(rewards: list[dict[str, Any]], tolerance: float = 0.05) -> bool:
    """Return whether alternate outcomes stay within the five-percent value rule."""
    budgets = [reward_budget(reward) for reward in rewards]
    if not budgets or max(budgets) <= 0:
        return True
    return (max(budgets) - min(budgets)) / max(budgets) <= tolerance


def _level_for_day(day: int) -> int:
    return min(50, 1 + day // 2)


def _floor_for_day(day: int) -> int:
    return min(45, 1 + day // 2)


def simulate_active_economy(days: int, *, daily_energy: int = 24) -> dict[str, Any]:
    """Project an active solo character using real sink formulas and a fixed routine.

    Sixteen energy are modeled as rewarded encounters; the remaining eight cover
    travel, gathering, authored rooms, and campaign scenes. Determinism makes this
    a stable release gate instead of a favorable random loot sequence.
    """
    days = max(1, int(days))
    balance = 40
    earned = 0
    spent = 0
    sanctum_queue = sorted(cost for definition in SANCTUM_ROOMS.values() for cost in definition["costs"])
    sanctum_index = 0
    ledger: list[dict[str, int]] = []

    for day in range(1, days + 1):
        level = _level_for_day(day)
        floor = _floor_for_day(day)
        rewarded_energy = min(daily_energy, 16)
        combat_income = round(rewarded_energy * (8 + floor * 1.55))
        objective_income = 90
        commission_income = 540 if day % 7 == 0 else 0
        story_income = 175 * min(6, 1 + day // 15) if day % 15 == 0 else 0
        income = combat_income + objective_income + commission_income + story_income
        balance += income
        earned += income
        # Active play budgets 65% of lifetime ordinary income toward services,
        # item work, and the Sanctum. The cumulative envelope absorbs lumpy
        # weekly/story rewards while guaranteeing meaningful savings.
        spend_allowance = max(0, round(earned * 0.65) - spent)

        rest_price = 18 + level * 4 + floor
        potion_price = 35 + level * 4 + floor
        craft_price = 80 + level * 12 + floor * 4
        planned = rest_price * 2 + potion_price
        if day % 2 == 0:
            planned += craft_price
        if day >= 7 and day % 2 == 1:
            planned += 80 + level * 5
        if day % 3 == 0:
            planned += round(craft_price * 0.75)

        sanctum_spend = 0
        if sanctum_index < len(sanctum_queue):
            cost = sanctum_queue[sanctum_index]
            if cost <= spend_allowance and balance >= cost + rest_price * 3:
                balance -= cost
                spent += cost
                sanctum_spend = cost
                sanctum_index += 1
                spend_allowance -= cost
        routine_spend = min(balance, planned, spend_allowance)
        balance -= routine_spend
        spent += routine_spend
        ledger.append({"day": day, "earned": income, "spent": routine_spend + sanctum_spend, "balance": balance})

    ratio = spent / earned if earned else 0.0
    return {
        "days": days,
        "earned": earned,
        "spent": spent,
        "saved": balance,
        "sink_ratio": ratio,
        "within_target": TARGET_SINK_RANGE[0] <= ratio <= TARGET_SINK_RANGE[1],
        "sanctum_upgrades": sanctum_index,
        "ledger": ledger,
    }


def economy_release_gate() -> dict[int, dict[str, Any]]:
    """Return the required 7-, 30-, and 90-day economy projections."""
    return {days: simulate_active_economy(days) for days in (7, 30, 90)}
