"""Normalisation + matching for trainer answers.

The compact answer string from sdamgia.ru looks like
``"всёравно"`` for a single accepted form, or ``"всамомделе|ведутсебя"``
for several accepted variants, with no spaces inside any variant.

We accept the user's answer if a normalised version of their input matches
any of the normalised variants.
"""
from __future__ import annotations

import re

_DASH_CHARS = "-‐‑‒–—―−"
_DASH_RE = re.compile(f"[{_DASH_CHARS}]")
_PUNCT_RE = re.compile(r"[.,;:!?\"'«»()\[\]]")


def normalise(s: str) -> str:
    """Reduce a Russian phrase to a canonical comparable form.

    - case-folded
    - ё → е (sdamgia is inconsistent about ё)
    - dashes/hyphens collapsed to nothing (so "крест-накрест" matches "крестнакрест")
    - punctuation stripped
    - all whitespace removed (so user can type with or without spaces)
    """
    s = s.strip().lower()
    s = s.replace("ё", "е")
    s = _DASH_RE.sub("", s)
    s = _PUNCT_RE.sub("", s)
    s = re.sub(r"\s+", "", s)
    return s


def variants_of(compact: str) -> list[str]:
    """Split sdamgia's pipe-joined compact answer into normalised variants."""
    return [normalise(v) for v in compact.split("|") if v.strip()]


def is_correct(user_input: str, compact_answer: str) -> bool:
    if not user_input or not compact_answer:
        return False
    return normalise(user_input) in variants_of(compact_answer)
