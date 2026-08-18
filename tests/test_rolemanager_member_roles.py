from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rolemanager.rolemanager import RoleManager


@dataclass(frozen=True)
class FakeRole:
    name: str
    position: int
    default: bool = False

    @property
    def mention(self) -> str:
        return f"@{self.name}"

    def is_default(self) -> bool:
        return self.default


@dataclass
class FakeGuild:
    roles: list[FakeRole]


@dataclass
class FakeMember:
    roles: list[FakeRole]


class FakeRoleConfig:
    def __init__(self, data: dict[str, bool]) -> None:
        self.data = data

    async def all(self) -> dict[str, bool]:
        return self.data


class FakeConfig:
    def __init__(self, data: dict[FakeRole, dict[str, bool]]) -> None:
        self.data = data

    def role(self, role: FakeRole) -> FakeRoleConfig:
        return FakeRoleConfig(self.data[role])


def test_member_self_role_list_filters_and_marks_roles() -> None:
    everyone = FakeRole("everyone", 0, default=True)
    available = FakeRole("Available", 1)
    assigned = FakeRole("Assigned", 2)
    locked = FakeRole("Locked", 3)
    hidden = FakeRole("Hidden", 4)
    unrelated = FakeRole("Unrelated", 5)
    guild = FakeGuild([everyone, available, assigned, locked, hidden, unrelated])
    member = FakeMember([assigned, locked])
    config = FakeConfig(
        {
            available: {"self_assignable": True, "self_removable": True, "self_listed": True},
            assigned: {"self_assignable": True, "self_removable": True, "self_listed": True},
            locked: {"self_assignable": True, "self_removable": False, "self_listed": True},
            hidden: {"self_assignable": True, "self_removable": True, "self_listed": False},
            unrelated: {"self_assignable": False, "self_removable": False, "self_listed": True},
        },
    )
    cog = object.__new__(RoleManager)
    cog.config = config

    pages = asyncio.run(cog._self_role_status_pages(guild, member))

    output = "\n".join(pages)
    assert "❌ not assigned — @Available" in output
    assert "✅ assigned — @Assigned" in output
    assert "✅ assigned (not self-removable) — @Locked" in output
    assert "Hidden" not in output
    assert "Unrelated" not in output


def test_existing_self_roles_default_to_visible() -> None:
    role = FakeRole("Legacy", 1)
    guild = FakeGuild([role])
    member = FakeMember([])
    cog = object.__new__(RoleManager)
    cog.config = FakeConfig(
        {role: {"self_assignable": True, "self_removable": True}},
    )

    pages = asyncio.run(cog._self_role_status_pages(guild, member))

    assert pages == ["❌ not assigned — @Legacy"]
