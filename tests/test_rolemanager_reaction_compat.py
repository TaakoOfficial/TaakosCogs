"""Tests for RoleManager's imported reaction-role compatibility layer."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "rolemanager" / "reaction_compat.py"
SPEC = importlib.util.spec_from_file_location("rolemanager_reaction_compat_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load RoleManager reaction compatibility helpers.")
compat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compat
SPEC.loader.exec_module(compat)


class EmojiCompatibilityTests(unittest.TestCase):
    def test_custom_emoji_formats_use_the_numeric_id(self):
        self.assertEqual(compat.canonical_emoji_key("<:games:123456789>"), "123456789")
        self.assertEqual(compat.canonical_emoji_key("<a:dance:987654321>"), "987654321")

    def test_unicode_variation_selectors_do_not_change_identity(self):
        self.assertEqual(compat.canonical_emoji_key("❤️"), compat.canonical_emoji_key("❤"))

    def test_imported_bindings_are_normalized_and_invalid_roles_are_removed(self):
        bindings = {
            "<:games:123456789>": {
                "role_id": "42",
                "emoji": "<:games:123456789>",
                "remove_on_unreact": 1,
            },
            "broken": {"role_id": "not-an-id", "emoji": "✅"},
        }

        normalized, changes = compat.normalize_reaction_bindings(bindings)

        self.assertGreater(changes, 0)
        self.assertEqual(set(normalized), {"123456789"})
        self.assertEqual(normalized["123456789"]["role_id"], 42)
        self.assertTrue(normalized["123456789"]["remove_on_unreact"])


if __name__ == "__main__":
    unittest.main()
