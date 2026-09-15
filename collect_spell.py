#!/usr/bin/env python3
"""
Collect ЕГЭ tasks №13–14 (слитное / дефисное / раздельное написание) from
rus-ege.sdamgia.ru and turn them into one-sentence training items.

The exam shows five sentences and asks which of them spell the highlighted
word(s) together. That is answerable by elimination, so it is a poor training
unit: here every sentence becomes its own item, and every highlighted word in
it its own question — "(НЕ)ИЗВЕСТНОМУ" → «неизвестному».

The correct spelling is recovered from the sdamgia разбор, which repeats each
sentence with the brackets opened. A task is kept only when every one of its
sentences could be read that way *and* the readings agree with the answer key:
the key sentences must all spell the asked way, the others must not. Anything
else is dropped — a trainer that grades wrongly is worse than a smaller bank.

Writes out/spell.json.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import collect
import collect_ortho as co

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

BASE = collect.EGE_BASE

SOURCES: dict[int, dict[int, str]] = {
    13: {
        384: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        373: "Задания для подготовки",
        207: "Тренировочные и диагностические работы",
    },
    14: {
        385: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        374: "Задания для подготовки",
        329: "Тренировочные и диагностические работы",
    },
}

TOPICS = {
    13: "Правописание НЕ и НИ",
    14: "Слитное, дефисное, раздельное написание слов",
}

PROMPT = "Раскрой скобки: как пишется выделенное слово в этом предложении?"

# How the three spellings are named, and how they are written.
TOGETHER, HYPHEN, APART = "together", "hyphen", "apart"
SEPARATOR = {TOGETHER: "", HYPHEN: "-", APART: " "}

CYR = "а-яёА-ЯЁ"
# "(НЕ)ИЗВЕСТНОМУ", "ДАВНЫМ(ДАВНО)", "КАК(БУДТО)" — brackets glued to letters,
# which is what separates a highlighted word from an ordinary aside.
TOKEN_RE = re.compile(
    rf"(?<![{CYR}])([{CYR}]*)\(([{CYR}]+)\)([{CYR}]*)(?![{CYR}])"
)


def norm(s: str) -> str:
    """Case- and ё-insensitive, length-preserving — spans stay usable."""
    return s.lower().replace("ё", "е")


def asked_spelling(prompt: str) -> str | None:
    p = prompt.upper()
    if "ДЕФИС" in p:
        return HYPHEN
    if "РАЗДЕЛЬНО" in p:
        return APART
    if "СЛИТНО" in p:
        return TOGETHER
    return None


def segments(explanation: str) -> dict[str, str]:
    """The разбор per sentence: "1) … 2) …" → {"1": "…"}."""
    marks = [(m.group(1), m.start()) for m in re.finditer(r"(?<!\d)([1-5])\s*\)", explanation)]
    out: dict[str, str] = {}
    for i, (n, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(explanation)
        chunk = re.sub(r"^[1-5]\s*\)\s*", "", explanation[pos:end])
        chunk = re.sub(r"\s*Ответ\s*:.*$", "", chunk, flags=re.S).strip(" ;,")
        if chunk and n not in out:
            out[n] = chunk
    return out


def _piece(text: str, spaced: bool) -> str:
    """The piece as a pattern. "spaced" tolerates a разбор that spells a word
    out to point at a morpheme: "НЕВИД ИМ ЫЕ", "НЕДО СТАЁТ"."""
    return r"\s*".join(map(re.escape, text)) if spaced else re.escape(text)


def read_token(parts: tuple[str, str, str], haystacks: list[str]) -> str | None:
    """How the разбор spells this word: together, hyphen, apart — or None."""
    left, inner, right = parts
    pieces = [p for p in (left, inner, right) if p]
    if len(pieces) != 2:
        return None
    for spaced in (False, True):
        pat = re.compile(
            rf"(?<![{CYR}])" + _piece(norm(pieces[0]), spaced)
            + r"(\s|-|‐|‑|)"
            + _piece(norm(pieces[1]), spaced) + rf"(?![{CYR}])"
        )
        found = set()
        for haystack in haystacks:
            for m in pat.finditer(norm(haystack)):
                sep = m.group(1)
                found.add(TOGETHER if not sep else (APART if sep.isspace() else HYPHEN))
            if found:
                break
        if len(found) == 1:
            return found.pop()
        if found:
            return None  # the разбор contradicts itself — do not guess
    return None


# Last resort: the разбор left the brackets closed and only named the rule.
PROSE = {TOGETHER: "слитн", HYPHEN: "дефис", APART: "раздельн"}


def read_prose(haystack: str) -> str | None:
    named = {k for k, word in PROSE.items() if word in norm(haystack)}
    return named.pop() if len(named) == 1 else None


def opened(token: str, spelling: str) -> str:
    left, inner, right = TOKEN_RE.fullmatch(token).groups()
    pieces = [p for p in (left, inner, right) if p]
    return SEPARATOR[spelling].join(pieces).lower()


def sentence_items(task: dict, stats: Counter) -> list[dict] | None:
    """Every sentence of one exam task, or None if the task cannot be trusted."""
    asked = asked_spelling(task["prompt"])
    if asked is None:
        stats["непонятный вопрос"] += 1
        return None
    segs = segments(task["explanation"])
    whole = re.sub(r"\s*Ответ\s*:.*$", "", task["explanation"], flags=re.S)

    items: list[dict] = []
    for no, sentence in sorted(task["sentences"].items()):
        tokens = list(TOKEN_RE.finditer(sentence))
        if not tokens:
            stats["нет выделенных слов"] += 1
            return None
        haystacks = [segs[no]] if no in segs else [whole]
        spellings = [read_token(m.groups(), haystacks) for m in tokens]
        if len(tokens) == 1 and spellings[0] is None:
            spellings = [read_prose(haystacks[0])]
        if any(s is None for s in spellings):
            stats["слова нет в разборе"] += 1
            return None
        # The key must agree: every word of a listed sentence spells the asked
        # way, and some word of an unlisted one does not.
        if all(s == asked for s in spellings) != (no in task["answer"]):
            stats["спорит с ключом"] += 1
            return None

        explanation = segs.get(no, whole)
        for i, (m, spelling) in enumerate(zip(tokens, spellings), start=1):
            # Show the other highlighted words already opened: one question
            # at a time, and their spelling gives this one away.
            shown = sentence
            for other, other_spelling in zip(tokens, spellings):
                if other is not m:
                    shown = shown.replace(other.group(0), opened(other.group(0), other_spelling).upper())
            if shown[-1] not in ".!?…":  # split_rows eats the full stop
                shown += "."
            items.append(
                {
                    "id": f"{task['id']}#{no}.{i}",
                    "source": "sdamgia",
                    "task_no": task["task_no"],
                    "topic": TOPICS[task["task_no"]],
                    "url": task["url"],
                    "prompt": PROMPT,
                    "sentence": shown,
                    "word": m.group(0),
                    "answer": opened(m.group(0), spelling),
                    "answer_kind": "spelling",
                    "explanation": explanation,
                }
            )
    return items


def collect_all() -> list[dict]:
    raw: list[dict] = []
    seen: set[int] = set()
    for task_no, cats in SOURCES.items():
        for cid, label in cats.items():
            url = f"{BASE}/test?filter=all&category_id={cid}&print=true"
            print(f"[fetch] №{task_no} — {label} (cat {cid})")
            page = collect.fetch(url, f"rus-ege_spell_cat_{cid}_print")
            for prob in co.parse_page(page):
                if prob["id"] in seen:
                    continue
                seen.add(prob["id"])
                prompt, sentences = co.split_rows(prob["question"])
                answer = re.sub(r"\D", "", prob["answer"].split("|")[0])
                if len(sentences) < 4 or not answer or not prob["explanation"]:
                    continue
                raw.append(
                    {
                        "id": f"sd{prob['id']}",
                        "task_no": task_no,
                        "url": f"{BASE}/problem?id={prob['id']}",
                        "prompt": prompt,
                        "sentences": {str(k): v for k, v in sorted(sentences.items())},
                        "answer": answer,
                        "explanation": prob["explanation"],
                    }
                )

    stats: Counter = Counter()
    out: list[dict] = []
    kept = 0
    for task in raw:
        items = sentence_items(task, stats)
        if items:
            out.extend(items)
            kept += 1
    print(f"[parse] задач {kept} из {len(raw)}, заданий {len(out)}")
    if stats:
        print("        отброшено: " + ", ".join(f"{k} {v}" for k, v in stats.most_common()))
    return out


if __name__ == "__main__":
    items = collect_all()
    by_no = Counter(t["task_no"] for t in items)
    print("        " + ", ".join(f"№{k}={v}" for k, v in sorted(by_no.items())))
    path = OUT_DIR / "spell.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {path}")
