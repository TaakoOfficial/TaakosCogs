"""Runtime-independent contracts for the new operations cogs."""

from __future__ import annotations

import asyncio

import pytest
from redbot.core import commands

from decisionledger.decisionledger import DecisionLedger
from decisionledger.models import compact_title, validate_transition
from eventcheckin.calendar_utils import build_calendar, escape_ics
from eventcheckin.eventcheckin import EventCheckin
from knowledgegarden.search import rank_entries
from secretsentinel.detection import find_secrets, redact
from serverdoctor.checks import Finding, analyze_snapshot, finding_changes


class FakeValue:
    def __init__(self, value: object) -> None:
        self.value = value

    def __call__(self) -> FakeValue:
        return self

    def __await__(self):
        async def resolve() -> object:
            return self.value

        return resolve().__await__()

    async def set(self, value: object) -> None:
        self.value = value


class FakeMappingValue(FakeValue):
    async def __aenter__(self) -> dict[str, object]:
        return self.value  # type: ignore[return-value]

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeGuildConfig:
    def __init__(self, **values: object) -> None:
        for name, value in values.items():
            wrapper = FakeMappingValue(value) if isinstance(value, dict) else FakeValue(value)
            setattr(self, name, wrapper)


class FakeConfig:
    def __init__(self, guild_config: FakeGuildConfig) -> None:
        self.guild_config = guild_config

    def guild(self, _guild: object) -> FakeGuildConfig:
        return self.guild_config


def test_secret_detection_reports_types_without_retaining_values() -> None:
    fake_github = "ghp_" + "A" * 36
    fake_aws = "AKIA" + "B" * 16
    text = f"tokens: {fake_github} and {fake_aws}"
    matches = find_secrets(text)
    assert {item.kind for item in matches} == {"GitHub token", "AWS access key"}
    cleaned = redact(text, matches)
    assert fake_github not in cleaned
    assert fake_aws not in cleaned
    assert cleaned.count("[REDACTED") == 2


def test_secret_detection_ignores_normal_identifiers() -> None:
    assert not find_secrets("issue ghp_short and ordinary AKIA text")


def test_serverdoctor_snapshot_severity_and_limits() -> None:
    findings = analyze_snapshot(
        {
            "required_bot_permissions": {"send_messages", "embed_links"},
            "bot_permissions": {"send_messages"},
            "everyone_dangerous_permissions": {"administrator"},
            "role_count": 230,
            "channel_count": 100,
            "bot_role_low": True,
            "empty_unmanaged_roles": 12,
        }
    )
    by_code = {item.code: item for item in findings}
    assert by_code["EVERYONE_DANGEROUS"].severity == "critical"
    assert by_code["BOT_PERMISSIONS"].detail == "embed_links"
    assert {"ROLE_LIMIT", "BOT_ROLE_LOW", "EMPTY_ROLES"} <= set(by_code)


def test_serverdoctor_reports_only_changed_finding_codes() -> None:
    findings = [
        Finding("BOT_PERMISSIONS", "high", "Missing permissions", "embed_links"),
        Finding("ROLE_LIMIT", "high", "Role limit", "230/250"),
    ]
    added, resolved = finding_changes(["BOT_PERMISSIONS", "EMPTY_ROLES"], findings)
    assert [item.code for item in added] == ["ROLE_LIMIT"]
    assert resolved == ["EMPTY_ROLES"]


def test_decision_transitions_and_title_cleanup() -> None:
    validate_transition("proposed", "accepted")
    validate_transition("accepted", "implemented")
    assert compact_title("  Adopt   office hours  ") == "Adopt office hours"
    try:
        validate_transition("proposed", "implemented")
    except ValueError as error:
        assert "cannot move" in str(error)
    else:
        raise AssertionError("invalid transition accepted")


def test_knowledge_search_weights_title_and_excludes_drafts() -> None:
    entries = [
        {
            "entry_id": 1,
            "title": "Reset two factor authentication",
            "body": "Ask staff",
            "tags": ["account"],
            "status": "published",
            "updated_at": 1,
        },
        {
            "entry_id": 2,
            "title": "Account help",
            "body": "Reset authentication with backup codes",
            "tags": [],
            "status": "published",
            "updated_at": 2,
        },
        {"entry_id": 3, "title": "Reset authentication", "body": "Draft", "tags": [], "status": "draft", "updated_at": 3},
    ]
    ranked = rank_entries(entries, "reset authentication")
    assert [entry["entry_id"] for _score, entry in ranked] == [1, 2]


def test_knowledge_search_uses_alternate_phrases() -> None:
    entries = [
        {
            "entry_id": 1,
            "title": "Two-factor authentication",
            "body": "Use a backup code.",
            "tags": [],
            "aliases": ["lost phone", "new authenticator"],
            "status": "published",
            "updated_at": 1,
        }
    ]
    ranked = rank_entries(entries, "lost phone")
    assert ranked[0][1]["entry_id"] == 1
    assert ranked[0][0] >= 10


def test_calendar_export_is_stable_and_escapes_text() -> None:
    payload = build_calendar(
        42,
        "Example, Guild",
        [
            {
                "event_id": 7,
                "title": "Workshop; Q&A",
                "description": "Line one\nLine two",
                "location": "Discord",
                "starts_at": 1_800_000_000,
                "duration_minutes": 90,
                "status": "open",
            }
        ],
        1_700_000_000,
    )
    assert payload.startswith("BEGIN:VCALENDAR\r\n")
    assert "UID:eventcheckin-42-7@discord.red" in payload
    assert "SUMMARY:Workshop\\; Q&A" in payload
    assert "DESCRIPTION:Line one\\nLine two" in payload
    assert escape_ics("a,b;c") == "a\\,b\\;c"


def test_eventcheckin_integration_service_creates_bounded_draft() -> None:
    guild_config = FakeGuildConfig(next_event_id=4, events={})
    cog = EventCheckin.__new__(EventCheckin)
    cog.config = FakeConfig(guild_config)
    cog._now = lambda: 1_700_000_000

    event = asyncio.run(
        cog.create_draft_service(
            object(),
            actor_id=12,
            starts_at=1_800_000_000,
            capacity=25,
            title="Quarterly review",
            duration_minutes=90,
            source_type="decisionledger",
            source_id=8,
        )
    )

    assert event["event_id"] == 4
    assert event["source_type"] == "decisionledger"
    assert event["source_id"] == 8
    assert guild_config.events.value["4"] is event
    assert guild_config.next_event_id.value == 5


def test_eventcheckin_integration_service_rejects_invalid_window() -> None:
    cog = EventCheckin.__new__(EventCheckin)
    cog.config = FakeConfig(FakeGuildConfig(next_event_id=1, events={}))
    cog._now = lambda: 100

    with pytest.raises(commands.BadArgument, match="future"):
        asyncio.run(
            cog.create_draft_service(
                object(),
                actor_id=12,
                starts_at=100,
                capacity=0,
                title="Past event",
            )
        )


def test_decisionledger_imports_once_and_keeps_source_link() -> None:
    guild_config = FakeGuildConfig(next_id=2, decisions={})
    cog = DecisionLedger.__new__(DecisionLedger)
    cog.config = FakeConfig(guild_config)
    cog._now = lambda: 1_700_000_000

    decision = asyncio.run(
        cog._create_imported(
            object(),
            title="  Fix   the handoff  ",
            rationale="Incident follow-up",
            actor_id=4,
            source_type="opsroom",
            source_key="opsroom:7:3",
            source_url="https://discord.com/channels/1/2",
            owner_id=9,
        )
    )

    assert decision["title"] == "Fix the handoff"
    assert decision["source_key"] == "opsroom:7:3"
    assert guild_config.next_id.value == 3
    with pytest.raises(commands.BadArgument, match="already Decision #2"):
        asyncio.run(
            cog._create_imported(
                object(),
                title="Duplicate",
                rationale="Duplicate",
                actor_id=4,
                source_type="opsroom",
                source_key="opsroom:7:3",
                source_url="",
            )
        )
