"""Focused tests for YALC's Discord-independent logging core."""

from __future__ import annotations

import datetime
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit = load_module("yalc_audit_test", "yalc/audit.py")
models = load_module("yalc_models_test", "yalc/models.py")
storage = load_module("yalc_storage_test", "yalc/storage.py")
proxy_detection = load_module("yalc_proxy_detection_test", "yalc/proxy_detection.py")


class FakeEntry:
    def __init__(self, entry_id, guild_id, action, target_id, *, channel_id=None):
        self.id = entry_id
        self.guild = types.SimpleNamespace(id=guild_id)
        self.action = types.SimpleNamespace(name=action)
        self.target = types.SimpleNamespace(id=target_id)
        self.extra = types.SimpleNamespace(channel_id=channel_id)
        self.created_at = datetime.datetime.now(datetime.timezone.utc)


class AuditCorrelatorTests(unittest.TestCase):
    def test_never_substitutes_an_unrelated_target(self):
        correlator = audit.AuditCorrelator()
        correlator.record(FakeEntry(1, 10, "ban", 100))

        self.assertIsNone(correlator.match(10, "ban", target_id=999))

    def test_matches_exact_target_and_deduplicates_entry_ids(self):
        correlator = audit.AuditCorrelator()
        entry = FakeEntry(1, 10, "ban", 100)

        self.assertTrue(correlator.record(entry))
        self.assertFalse(correlator.record(entry))
        match = correlator.match(10, "ban", target_id=100)

        self.assertIsNotNone(match)
        self.assertIs(match.entry, entry)
        self.assertEqual(match.confidence, "confirmed")
        self.assertEqual(correlator.stats()["duplicates"], 1)

    def test_channel_only_events_require_the_same_channel(self):
        correlator = audit.AuditCorrelator()
        correlator.record(FakeEntry(2, 10, "message_delete", 100, channel_id=20))

        self.assertIsNone(correlator.match(10, "message_delete", channel_id=21))
        self.assertIsNotNone(correlator.match(10, "message_delete", channel_id=20))


class LogEventTests(unittest.TestCase):
    def test_message_content_is_opt_in(self):
        event = models.LogEvent(
            guild_id=1,
            event_type="message_edit",
            summary="edited",
            details={"before_content": "secret", "after_content": "new", "message_id": 2},
        )

        private_payload = event.journal_payload(include_content=False)
        content_payload = event.journal_payload(include_content=True)

        self.assertNotIn("before_content", private_payload["details"])
        self.assertNotIn("after_content", private_payload["details"])
        self.assertEqual(content_payload["details"]["before_content"], "secret")


class EventJournalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.journal = storage.EventJournal(Path(self.temp_dir.name) / "events.sqlite3")
        await self.journal.initialize()

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_add_search_dedupe_and_delete_user(self):
        event = models.LogEvent(
            guild_id=1,
            event_type="member_ban",
            summary="User was banned",
            actor_id=10,
            target_id=20,
            audit_entry_id=30,
        )
        await self.journal.add(event, include_content=False)
        await self.journal.add(event, include_content=False)
        related_event = models.LogEvent(
            guild_id=1,
            event_type="member_ban",
            summary="A second target was banned in the same audited operation",
            actor_id=10,
            target_id=21,
            audit_entry_id=30,
        )
        await self.journal.add(related_event, include_content=False)

        rows = await self.journal.search(1, query="banned", event_type="member_ban")
        self.assertEqual(len(rows), 2)
        self.assertEqual((await self.journal.stats(1))["count"], 2)

        self.assertEqual(await self.journal.delete_user(20), 1)
        self.assertEqual((await self.journal.stats(1))["count"], 1)


class DashboardRoutingRegressionTests(unittest.TestCase):
    def test_removed_event_group_mapping_is_not_referenced(self):
        for relative_path in ("yalc/dashboard_integration.py", "yalc/yalc.py"):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("EVENT_TO_SETUP_GROUP", source, relative_path)


class ProxyDetectionTests(unittest.TestCase):
    def test_proxy_ids_are_normalized_across_config_types(self):
        self.assertEqual(
            proxy_detection.normalize_proxy_ids(["431544605209788416", 466378653216014359, "bad"]),
            {431544605209788416, 466378653216014359},
        )

    def test_tupperbox_application_metadata_is_detected(self):
        self.assertTrue(
            proxy_detection.proxy_metadata_matches(
                configured_ids=[],
                webhook_id=123,
                application_id=431544605209788416,
                author_name="Arbitrary persona name",
            ),
        )

    def test_webhook_owner_identifies_proxy_with_arbitrary_persona(self):
        self.assertTrue(
            proxy_detection.proxy_metadata_matches(
                configured_ids=["999"],
                webhook_id=123,
                webhook_owner_id="999",
                author_name="Character Name",
            ),
        )

    def test_unrelated_bot_content_is_not_treated_as_proxy(self):
        self.assertFalse(
            proxy_detection.proxy_metadata_matches(
                configured_ids=[],
                author_id=123,
                author_is_bot=True,
                author_name="Status Bot",
            ),
        )


if __name__ == "__main__":
    unittest.main()
