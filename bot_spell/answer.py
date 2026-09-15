"""Answer normalisation for the слитно/раздельно/дефис trainer.

One sentence, one highlighted word in brackets — "(НЕ)ИЗВЕСТНОМУ" — and the
answer is that word with the brackets opened: «неизвестному», «не известному»
or «давным-дефис-давно». So the separator *is* the answer, and unlike the
other trainers we must not throw spaces and hyphens away.

Case and ё/е are ignored, as are surrounding punctuation and doubled spaces.
"""
from __future__ import annotations

import re

_KEEP_RE = re.compile(r"[^а-я \-]")
_HYPHENS = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
_SPACES_RE = re.compile(r"\s+")


def normalise(s: str) -> str:
    """" — НЕ ДОЖИДАЯСЬ, " → "не дожидаясь"."""
    s = (s or "").lower().replace("ё", "е").translate(_HYPHENS)
    s = _SPACES_RE.sub(" ", _KEEP_RE.sub(" ", s))
    return re.sub(r" ?- ?", "-", s).strip(" -")


def is_correct(user_input: str, expected: str) -> bool:
    user = normalise(user_input)
    return bool(user) and user == normalise(expected)


def looks_like_answer(s: str) -> bool:
    """A word, or two or three words — not a sentence and not a shrug."""
    text = normalise(s)
    return bool(text) and len(text) <= 40 and len(text.split(" ")) <= 3
