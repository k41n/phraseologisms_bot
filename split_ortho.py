#!/usr/bin/env python3
"""
Split the row-number tasks of out/ortho.json into one item per row:
out/ortho_rows.json.

The exam question ("укажите ряды, где пропущена одна и та же буква") shows five
rows and is answered with row numbers. For training that is a poor unit: the
child can score it by elimination without knowing a single word. So every row
becomes its own item, answered with the missing letters themselves:

    оп..раться, см..нать (траву), поч..татель (таланта)   →   и, и, и

The letters are recovered from the sdamgia разбор, which spells every word out
("оп и раться"). A row is kept only when

  * every word has exactly one gap and exactly one candidate letter, and
  * the letters agree with the original answer key — all equal for a row listed
    in the key, not all equal for a row that is not.

Rows that fail either check are dropped: a trainer that grades wrongly is worse
than a smaller bank. Tasks that are already a single question — ФИПИ's
"выпишите слово" and №15's sentence with numbered gaps — are copied over
untouched.
"""
from __future__ import annotations

import itertools
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"

GAP_RE = re.compile(r"\.{2,}|_+|…")
ACCENT_RE = re.compile("[\u0300\u0301]")  # stress marks only — keep ё and й intact
GAP = ".."

PROMPT = (
    "Вставьте пропущенные буквы. "
    "Запишите их через запятую в том же порядке, что и слова."
)


# --- reading a row ----------------------------------------------------------


def split_words(row: str) -> list[str]:
    """Split on commas and semicolons, but not inside "(траву)"."""
    words, buf, depth = [], "", 0
    for ch in row:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch in ",;" and depth == 0:
            words.append(buf)
            buf = ""
        else:
            buf += ch
    words.append(buf)
    return [w.strip() for w in words if w.strip()]


def display_word(word: str) -> str:
    """Drop the footnote gloss sdamgia appends after "*", unify the gap mark."""
    head = word.split("*")[0].strip() or word.replace("*", "").strip()
    return GAP_RE.sub(GAP, head)


def match_word(word: str) -> str:
    """The word as it is looked up in the разбор: no gloss, no parentheses."""
    return re.sub(r"\([^)]*\)", "", display_word(word)).strip()


# --- reading the разбор -----------------------------------------------------


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return unicodedata.normalize("NFC", ACCENT_RE.sub("", s)).lower()


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def segments(explanation: str) -> dict[str, list[str]]:
    """The разбор per row: "1) … 2) …" → {"1": ["…"], "2": ["…"]}.

    A разбор often walks the rows twice — a bare "1) з а ночевать" pass and a
    detailed one with the rules — so every chunk marked with the row number is
    collected. A chunk ends at the next marker, whichever row it belongs to.
    """
    marks = [(m.group(1), m.start()) for m in re.finditer(r"(?<!\d)([1-5])\s*\)", explanation)]
    out: dict[str, list[str]] = {}
    for i, (n, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(explanation)
        chunk = re.sub(r"^[1-5]\s*\)\s*", "", explanation[pos:end])
        chunk = re.sub(r"\s*Ответ\s*:.*$", "", chunk, flags=re.S)
        chunk = re.sub(r"\s+", " ", chunk).strip(" ;,.")
        if chunk:
            out.setdefault(n, []).append(chunk)
    return out


def candidates(word: str, haystacks: list[tuple[str, bool]]) -> set[str] | None:
    """Letters that fit the gap according to the разбор; None if unusable."""
    body = match_word(word)
    if body.count(GAP) != 1:
        return None
    prefix, suffix = (squash(norm(p)) for p in body.split(GAP))
    if not prefix and not suffix:
        return None
    for haystack, whole_word in haystacks:
        if whole_word:
            pat = re.compile(
                r"(?<![а-яё])" + re.escape(prefix) + r"([а-яё])" + re.escape(suffix) + r"(?![а-яё])"
            )
        else:
            # The разбор often spaces a word out ("рас ст и л а ть"), which
            # destroys word boundaries — match inside the squashed text.
            pat = re.compile(re.escape(prefix) + r"([а-яё])" + re.escape(suffix))
        found = {m.group(1) for m in pat.finditer(haystack)}
        if found:
            return found
    return set()


def solve_row(
    task: dict, chunks: list[str], words: list[str], same: bool, stats: Counter
) -> list[str] | None:
    whole = norm(task.get("explanation") or "")
    part = norm(" ".join(chunks)) or whole
    haystacks = [(part, True), (whole, True), (squash(part), False), (squash(whole), False)]

    per_word = [candidates(w, haystacks) for w in words]
    if any(c is None for c in per_word):
        stats["двойной пропуск"] += 1
        return None
    if any(not c for c in per_word):
        stats["нет слова в разборе"] += 1
        return None

    fits = [
        combo
        for combo in itertools.product(*(sorted(c) for c in per_word))
        if (len(set(combo)) == 1) == same
    ]
    if len(fits) != 1:
        stats["неоднозначно" if fits else "спорит с ключом"] += 1
        return None
    return list(fits[0])


# --- building the bank ------------------------------------------------------


def row_items(task: dict, stats: Counter) -> list[dict]:
    items = []
    segs = segments(task.get("explanation") or "")
    for no, row in sorted(task["rows"].items()):
        words = split_words(row)
        if len(words) < 2:
            stats["меньше двух слов"] += 1
            continue
        shown = [display_word(w) for w in words]
        chunks = segs.get(no, [])
        letters = solve_row(task, chunks, words, no in task["answer"], stats)
        if letters is None:
            continue
        items.append(
            {
                "id": f"{task['id']}#{no}",
                "source": task["source"],
                "task_no": task["task_no"],
                "topic": task["topic"],
                "url": task.get("url", ""),
                "prompt": PROMPT,
                "row": ", ".join(shown),
                "words": shown,
                "answer": ", ".join(letters),
                "answer_kind": "letters",
                # The fullest pass over this row is the one worth showing.
                "explanation": max(chunks, key=len, default=task.get("explanation") or ""),
            }
        )
    return items


def main() -> None:
    bank = json.loads((OUT / "ortho.json").read_text(encoding="utf-8"))
    stats: Counter = Counter()
    out: list[dict] = []
    whole_tasks = 0
    for task in bank:
        if task.get("answer_kind", "rows") != "rows":
            out.append(task)
            whole_tasks += 1
            continue
        out.extend(row_items(task, stats))

    by_no: Counter = Counter(t["task_no"] for t in out)
    print(
        f"[split] {len(out)} заданий — рядов {len(out) - whole_tasks}, "
        f"целиком {whole_tasks}"
    )
    print("        " + ", ".join(f"№{k}={v}" for k, v in sorted(by_no.items())))
    print("        пропущено: " + ", ".join(f"{k} {v}" for k, v in stats.most_common()))
    path = OUT / "ortho_rows.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {path}")


if __name__ == "__main__":
    main()
