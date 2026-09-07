"""Answer normalisation for the orthography trainer.

Tasks №9–12 are shown one row at a time, so the answer is the missing letters
of that row, in word order: "и, и, и". Order matters, separators do not, and
case and ё/е are ignored — «е» typed for «ё» is accepted.

Some ФИПИ tasks instead ask to write out the word (or the pair of words) with
the missing letter filled in. Those are graded on letters alone too.

The row-number form ("124") is still understood: it is what the exam itself
asks for, and older banks are graded with it.
"""
from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"[1-5]")
_NON_LETTER_RE = re.compile(r"[^а-я]")
_SEPARATOR_RE = re.compile(r"[\s,.;:/|+\-–—]+")


def normalise(s: str) -> str:
    """"4, 2 и 1" → "124"; anything without digits 1–5 → ""."""
    return "".join(sorted(set(_DIGITS_RE.findall(s or ""))))


def normalise_word(s: str) -> str:
    """"Приволье, приуныть" → "привольеприуныть"."""
    return _NON_LETTER_RE.sub("", (s or "").lower().replace("ё", "е"))


def normalise_letters(s: str) -> str:
    """"Ь, ь, Ъ" → "ььъ" — the letters in the order they were typed."""
    return normalise_word(s)


def is_correct(user_input: str, expected: str, kind: str = "rows") -> bool:
    if kind == "letters":
        user = normalise_letters(user_input)
        return bool(user) and user == normalise_letters(expected)
    if kind == "word":
        user = normalise_word(user_input)
        return bool(user) and user == normalise_word(expected)
    user = normalise(user_input)
    return bool(user) and user == normalise(expected)


def looks_like_answer(s: str, kind: str = "rows") -> bool:
    """True if the message is plausibly an answer of the given kind."""
    if kind == "letters":
        # Up to four letters and nothing else: "ь, ь, ъ", "ььъ", "ь ь ъ".
        return bool(re.fullmatch(r"[а-яё]{1,4}", _SEPARATOR_RE.sub("", (s or "").lower())))
    if kind == "word":
        return bool(normalise_word(s))
    return bool(s) and bool(_DIGITS_RE.search(s)) and not re.search(r"[а-яa-z]", s.lower())
