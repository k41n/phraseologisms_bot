"""Tests for the answer-matching logic.

Run from the project root with:

    python -m pytest bot/tests
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import answer  # noqa: E402


def test_exact_match():
    assert answer.is_correct("всё равно", "всёравно")


def test_user_typed_without_spaces():
    assert answer.is_correct("всёравно", "всёравно")


def test_yo_to_ye_equivalence():
    assert answer.is_correct("все равно", "всёравно")
    assert answer.is_correct("всё равно", "всеравно")


def test_case_insensitive():
    assert answer.is_correct("Всё Равно", "всёравно")
    assert answer.is_correct("ВСЁ РАВНО", "всёравно")


def test_trims_outer_whitespace():
    assert answer.is_correct("   всё равно   ", "всёравно")


def test_strips_trailing_punctuation():
    assert answer.is_correct("всё равно.", "всёравно")
    assert answer.is_correct("«всё равно»", "всёравно")


def test_multiple_accepted_variants():
    compact = "махнутьрукой|махнулирукой|немахнутьрукой|немахнулирукой"
    assert answer.is_correct("махнули рукой", compact)
    assert answer.is_correct("не махнуть рукой", compact)
    assert not answer.is_correct("отвели руки", compact)


def test_hyphenated_phrase():
    assert answer.is_correct("крест-накрест", "крест-накрест")
    assert answer.is_correct("крест накрест", "крест-накрест")
    assert answer.is_correct("крестнакрест", "крест-накрест")


def test_em_dash_in_user_input():
    # User pastes from a richtext source that gave them an em-dash
    assert answer.is_correct("крест—накрест", "крест-накрест")


def test_wrong_phrase_rejected():
    assert not answer.is_correct("спустя рукава", "всёравно")


def test_empty_inputs():
    assert not answer.is_correct("", "всёравно")
    assert not answer.is_correct("всё равно", "")
    assert not answer.is_correct("", "")


def test_partial_match_rejected():
    # User types only half the phraseologism
    assert not answer.is_correct("всё", "всёравно")
    assert not answer.is_correct("равно", "всёравно")
