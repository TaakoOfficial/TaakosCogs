"""Regression tests for DeepDelve bestiary portrait coverage."""

from __future__ import annotations

from deepdelve.art import bestiary_slug, combat_art_path
from deepdelve.content import BOSSES, ENEMIES


def test_every_core_creature_and_boss_has_an_optimized_portrait() -> None:
    roster = (*ENEMIES, *BOSSES)
    paths = [combat_art_path(entry) for entry in roster]

    assert len(roster) == 33
    assert all(path is not None for path in paths)
    assert len(set(paths)) == len(roster)
    assert all(path.suffix == ".webp" for path in paths if path)


def test_modified_encounters_reuse_their_base_portrait() -> None:
    base = combat_art_path({"name": "Cave Rat"})

    assert combat_art_path({"name": "Riftbound Cave Rat", "base_name": "Cave Rat"}) == base
    assert combat_art_path({"name": "The Drowned Sexton", "art_name": "Cave Rat"}) == base
    assert combat_art_path({"name": "Unknown", "base_name": "Missing"}) is None


def test_bestiary_slugs_are_stable_for_punctuation() -> None:
    assert bestiary_slug("Yesterday's Corpse") == "yesterday-s-corpse"
    assert bestiary_slug("Saint Caligo, Unremembered") == "saint-caligo-unremembered"
