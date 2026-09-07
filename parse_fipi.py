#!/usr/bin/env python3
"""
Parse the ЕГЭ open bank pages (ege.fipi.ru) cached under cache/fipi/ and keep
the orthography tasks that correspond to ЕГЭ №9–12.

The bank publishes no answers — see solve_fipi.py, which fills them in.
Writes out/ortho_fipi.json.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import collect

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "fipi"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

PROJ = "AF0ED3F2557F8FFC4C06F80B6803FD26"

# КЭС prefixes that can hold a №9–12 task. The exam number is decided by the
# question wording (see classify), because one КЭС feeds several task numbers.
KES_KEEP = ("3.7.2", "3.7.3", "3.7.4", "3.7.5", "3.7.8")

TOPICS = {
    9: "Правописание корней",
    10: "Правописание приставок",
    11: "Правописание суффиксов (кроме -Н-/-НН-)",
    12: "Правописание личных окончаний глаголов и суффиксов причастий",
}

BLOCK_RE = re.compile(
    r"<div class=\"qblock\" id='q(?P<short>[0-9A-F]+)'>(?P<body>.*?)"
    r"(?=<div class=\"qblock\" id='q|</body>)",
    re.S,
)
GUID_RE = re.compile(r'name="guid" value="([0-9a-fA-F]+)"')
PROMPT_RE = re.compile(r"class='cell_0'>(?P<p>.*?)</TD>", re.S)
ROW_RE = re.compile(
    r"<input type=\"checkbox\" name=\"test(?P<i>\d+)\".*?(?:<b>)?(?P<n>\d+)\)(?:</b>)?&nbsp;</td>.*?"
    r"<td width=\"100%\"[^>]*>(?P<text>.*?)</td>",
    re.S,
)
KES_RE = re.compile(r'КЭС:</td><td class="param-row"><div>(?P<kes>[^<]*)</div>')
ANSWER_TYPE_RE = re.compile(r'Тип ответа:</td><td>([^<]*)</td>')
# Older free-text tasks ("выпишите слово, в котором пишется буква И") list their
# candidate words in a plain table right after the prompt paragraph.
PROMPT_P_RE = re.compile(r'<p class="?MsoNormal"?[^>]*>(?P<p>.*?)</p>', re.S)
WORD_OPTION_RE = re.compile(
    r'<td width="100%" align=left><p class="?MsoNormal"?[^>]*>(?P<w>.*?)</p>', re.S
)


def text_of(fragment: str) -> str:
    return collect.clean_text(collect.strip_tags(fragment))


def classify(prompt: str, kes: str) -> int | None:
    """Map a task to its ЕГЭ number by the wording of the prompt."""
    p = prompt.lower()
    if "корн" in p:
        return 9
    if "приставк" in p:
        return 10
    if "личных окончаний глагол" in p or "суффиксов причаст" in p or "спряжен" in p:
        return 12
    if "суффикс" in p:
        return 11
    # Prompt is the generic "пропущена одна и та же буква" — fall back to КЭС.
    if kes.startswith("3.7.2"):
        return 9
    if kes.startswith(("3.7.3", "3.7.4")):
        return 10
    if kes.startswith("3.7.5"):
        return 11
    if kes.startswith("3.7.8"):
        return 12
    return None


def parse_all() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for page_path in sorted(CACHE.glob("page_*.html")):
        page = page_path.read_text(encoding="utf-8")
        for m in BLOCK_RE.finditer(page):
            body = m.group("body")
            kesm = KES_RE.search(body)
            kes = html.unescape(kesm.group("kes")).strip() if kesm else ""
            if not kes.startswith(KES_KEEP):
                continue
            guidm = GUID_RE.search(body)
            pm = PROMPT_RE.search(body)
            if not (guidm and pm):
                continue
            guid = guidm.group(1)  # case matters to solve.php
            if guid in seen:
                continue
            rows = {
                int(r.group("n")): text_of(r.group("text"))
                for r in ROW_RE.finditer(body)
            }
            cell = pm.group("p")
            first_p = PROMPT_P_RE.search(cell)
            prompt = text_of(first_p.group("p")) if first_p else text_of(cell)
            options: list[str] = []
            if len(rows) < 4:
                # Free-text variant: the candidate words sit in an unnumbered table.
                options = [text_of(w.group("w")) for w in WORD_OPTION_RE.finditer(cell)]
                options = [o for o in options if o and o != "\u00a0"]
                if len(options) < 4:
                    continue  # neither shape — skip
            task_no = classify(prompt, kes)
            if task_no is None:
                continue
            seen.add(guid)
            atype = ANSWER_TYPE_RE.search(body)
            out.append(
                {
                    "id": f"fipi{m.group('short')}",
                    "source": "fipi",
                    "guid": guid,
                    "task_no": task_no,
                    "topic": TOPICS[task_no],
                    "category": "Открытый банк ФИПИ",
                    "kes": kes,
                    "answer_type": text_of(atype.group(1)) if atype else "",
                    "url": f"https://ege.fipi.ru/bank/index.php?proj={PROJ}",
                    "prompt": prompt,
                    "answer_kind": "rows" if rows else "word",
                    "rows": {str(k): v for k, v in sorted(rows.items())}
                    or {str(i + 1): o for i, o in enumerate(options)},
                    "answer": "",
                    "explanation": "",
                }
            )
    return out


if __name__ == "__main__":
    tasks = parse_all()
    by_no: dict[int, int] = {}
    for t in tasks:
        by_no[t["task_no"]] = by_no.get(t["task_no"], 0) + 1
    print(f"[parsed] {len(tasks)} FIPI tasks: " + ", ".join(f"№{k}={v}" for k, v in sorted(by_no.items())))
    path = OUT_DIR / "ortho_fipi.json"
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {path}")
