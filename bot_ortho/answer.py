"""Answer normalisation for the orthography trainer.

Most tasks №9–12 are answered with the numbers of the rows where the same
letter is missing, e.g. "124": order and separators do not matter, so both
sides reduce to a sorted digit string.

Some ФИПИ tasks instead ask to write out the word (or the pair of words) with
the missing letter filled in. Those are graded on letters alone — case, ё/е,
spaces and punctuation are all ignored.
"""
from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"[1-5]")
_NON_LETTER_RE = re.compile(r"[^а-я]")


def normalise(s: str) -> str:
    """"4, 2 и 1" → "124"; anything without digits 1–5 → ""."""
    return "".join(sorted(set(_DIGITS_RE.findall(s or ""))))


def normalise_word(s: str) -> str:
    """"Приволье, приуныть" → "привольеприуныть"."""
    return _NON_LETTER_RE.sub("", (s or "").lower().replace("ё", "е"))


def is_correct(user_input: str, expected: str, kind: str = "rows") -> bool:
    if kind == "word":
        user = normalise_word(user_input)
        return bool(user) and user == normalise_word(expected)
    user = normalise(user_input)
    return bool(user) and user == normalise(expected)


def looks_like_answer(s: str, kind: str = "rows") -> bool:
    """True if the message is plausibly an answer of the given kind."""
    if kind == "word":
        return bool(normalise_word(s))
    return bool(s) and bool(_DIGITS_RE.search(s)) and not re.search(r"[а-яa-z]", s.lower())
