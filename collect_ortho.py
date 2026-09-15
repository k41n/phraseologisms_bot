#!/usr/bin/env python3
"""
Collect ЕГЭ orthography tasks (№9–12, №15) from rus-ege.sdamgia.ru.

Same pipeline as collect.py (print pages → parse → JSON), but the payload is
different: №9–12 are "выберите ряды, где пропущена одна и та же буква", so a
task is question + five numbered rows of words, and the answer is a set of row
numbers ("35"). №15 is one sentence with numbered gaps ("ра(2)их"), answered
with the digits that take -НН- (or, in the mirrored wording, a single -Н-).

Writes out/ortho_sdamgia.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import collect  # reuse fetch/cache + block parsing helpers

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

BASE = collect.EGE_BASE

# task number → {category_id: label}
SOURCES: dict[int, dict[int, str]] = {
    9: {
        380: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        259: "Задания для подготовки",
        358: "Тренировочные и диагностические работы",
    },
    10: {
        381: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        344: "Задания для подготовки",
        348: "Тренировочные и диагностические работы",
    },
    11: {
        382: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        343: "Задания для подготовки",
        351: "Тренировочные и диагностические работы",
    },
    12: {
        383: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        346: "Задания для подготовки",
        350: "Тренировочные и диагностические работы",
    },
    15: {
        386: "ОБЗ ФИПИ, демоверсии и прошедшие экзамены",
        214: "Задания для подготовки",
        297: "Задания на основе экзаменов прошлых лет",
        267: "Тренировочные и диагностические работы",
    },
}

TOPICS = {
    9: "Правописание корней",
    10: "Правописание приставок",
    11: "Правописание суффиксов (кроме -Н-/-НН-)",
    12: "Правописание личных окончаний глаголов и суффиксов причастий",
    15: "Правописание -Н- и -НН- в суффиксах",
}

# ---------------------------------------------------------------------- parsing
#
# The print pages for №9–12 and №15 have no reading text, so the block layout differs
# from collect.py's: each task is a <div class="prob_maindiv" id="maindivNNN">
# holding the question (#bodyNNN), the explanation (#solNNN) and a compact
# <div class="answer"> with the canonical digits.

BLOCK_RE = re.compile(
    r'<div[^>]*class="prob_maindiv"[^>]*id="maindiv(?P<mid>\d+)"[^>]*>(?P<body>.*?)'
    r'(?=<div[^>]*class="prob_maindiv"|<div[^>]*id="ans_key"|</body>)',
    re.S,
)
PROB_ID_RE = re.compile(r'/problem\?id=(\d+)')
QUESTION_RE = re.compile(r'id="body\d+"[^>]*class="pbody">(?P<q>.*?)</div>\s*</div>', re.S)
SOLUTION_RE = re.compile(r'id="sol\d+"[^>]*class="solution"[^>]*>(?P<s>.*?)</div>\s*<div class="answer"', re.S)
ANSWER_RE = re.compile(r'<div class="answer"[^>]*>\s*<span[^>]*>\s*Ответ:\s*([^<]*)</span>', re.S)


def parse_page(page: str) -> list[dict]:
    out: list[dict] = []
    for m in BLOCK_RE.finditer(page):
        body = m.group("body")
        pid = PROB_ID_RE.search(body)
        qm = QUESTION_RE.search(body)
        am = ANSWER_RE.search(body)
        if not (pid and qm and am):
            continue
        sm = SOLUTION_RE.search(body)
        out.append(
            {
                "id": int(pid.group(1)),
                "question": collect.clean_text(collect.strip_tags(qm.group("q"))),
                "explanation": collect.clean_text(collect.strip_tags(sm.group("s"))) if sm else "",
                "answer": collect.clean_text(am.group(1)).strip(". "),
            }
        )
    return out


# A row inside the task body: "1) выг..рать, пол..жение, ..." — sdamgia marks
# them with <p> or <br>; after tag stripping they read as "N) words".
ROW_RE = re.compile(r"(?<!\d)([1-5])\)\s*([^)]*?)(?=(?:[1-5]\)|$))", re.S)


def split_rows(question: str) -> tuple[str, dict[int, str]]:
    """Split "prompt 1) ... 2) ..." into the prompt and {row: words}."""
    first = re.search(r"(?<!\d)1\)", question)
    if not first:
        return question, {}
    prompt = question[: first.start()].strip()
    rows: dict[int, str] = {}
    body = question[first.start():]
    marks = list(re.finditer(r"(?<!\d)([1-5])\)", body))
    for i, m in enumerate(marks):
        n = int(m.group(1))
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        rows[n] = body[m.end():end].strip(" .;")
    return prompt, rows


# №15 has no rows: one sentence with numbered gaps ("ра(2)их"), answered with
# the digits where the doubled letter goes. The prompt asks for either НН or a
# single Н, so it must be kept verbatim.
SENTENCE_RE = re.compile(
    r"^(?P<prompt>.*?пишется\s+(?:только\s+)?(?:одна\s+буква\s+)?(?:НН|Н)\s*\.)"
    r"\s*(?P<sentence>.+)$",
    re.S,
)


def split_sentence(question: str) -> tuple[str, str]:
    """Split "Укажите цифру(-ы) … НН. Своеобразие художестве(1)ого …"."""
    m = SENTENCE_RE.match(question)
    if not m or "(1)" not in m.group("sentence"):
        return question, ""
    prompt = re.sub(r"\s+([.,])", r"\1", m.group("prompt").strip())
    # Some of the bank was OCR'd: a lone Cyrillic З stands in for the digit 3.
    sentence = re.sub(r"\(\s*[Зз]\s*\)", "(3)", m.group("sentence").strip())
    return prompt, sentence


def collect_all() -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    for task_no, cats in SOURCES.items():
        for cid, label in cats.items():
            url = f"{BASE}/test?filter=all&category_id={cid}&print=true"
            print(f"[fetch] №{task_no} — {label} (cat {cid})")
            page = collect.fetch(url, f"rus-ege_ortho_cat_{cid}_print")
            for prob in parse_page(page):
                if prob["id"] in seen:
                    continue
                seen.add(prob["id"])
                if task_no == 15:
                    prompt, sentence = split_sentence(prob["question"])
                    answer = prob["answer"]
                    gaps = set(re.findall(r"\((\d)\)", sentence))
                    # Every answered gap must exist in the sentence, or the
                    # sentence did not survive its trip through the parser.
                    # sdamgia lists each accepted permutation ("34|43").
                    digits = set(re.sub(r"\D", "", answer.split("|")[0]))
                    if not sentence or not digits or not digits <= gaps:
                        continue
                    out.append(
                        {
                            "id": f"sd{prob['id']}",
                            "source": "sdamgia",
                            "task_no": task_no,
                            "topic": TOPICS[task_no],
                            "category": label,
                            "url": f"{BASE}/problem?id={prob['id']}",
                            "prompt": prompt,
                            "sentence": sentence,
                            "answer": answer,
                            "answer_kind": "digits",
                            "explanation": prob["explanation"],
                        }
                    )
                    continue
                prompt, rows = split_rows(prob["question"])
                answer = prob["answer"]
                if not rows or not answer:
                    continue
                out.append(
                    {
                        "id": f"sd{prob['id']}",
                        "source": "sdamgia",
                        "task_no": task_no,
                        "topic": TOPICS[task_no],
                        "category": label,
                        "url": f"{BASE}/problem?id={prob['id']}",
                        "prompt": prompt,
                        "rows": {str(k): v for k, v in sorted(rows.items())},
                        "answer": answer,
                        "explanation": prob["explanation"],
                    }
                )
    return out


if __name__ == "__main__":
    tasks = collect_all()
    by_no: dict[int, int] = {}
    for t in tasks:
        by_no[t["task_no"]] = by_no.get(t["task_no"], 0) + 1
    print(f"[parsed] {len(tasks)} tasks: " + ", ".join(f"№{k}={v}" for k, v in sorted(by_no.items())))
    path = OUT_DIR / "ortho_sdamgia.json"
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {path}")
