#!/usr/bin/env python3
"""
Merge the two orthography sources into one bank: out/ortho.json.

  out/ortho_sdamgia.json  — 9–12 and 15 from rus-ege.sdamgia.ru (answer + разбор)
  out/ortho_fipi.json     — the same task types straight from the ФИПИ bank
  out/fipi_answers.json   — {guid: "digits"} filled in by solve_fipi.py

A ФИПИ task whose rows also appear on sdamgia is dropped in favour of the
sdamgia copy, which carries an explanation. ФИПИ tasks with no known answer
are dropped too — the trainer must always be able to grade.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"


def norm_row(s: str) -> str:
    s = s.lower().replace("ё", "е")
    s = re.sub(r"\([^)]*\)", "", s)          # drop clarifications like "(траву)"
    return re.sub(r"[^а-я]", "", s)


def row_key(task: dict) -> tuple:
    """What makes two tasks the same: their rows, or №15's sentence."""
    if "rows" not in task:
        return (norm_row(task["sentence"]),)
    return tuple(sorted(norm_row(v) for v in task["rows"].values()))


def canon_answer(ans: str) -> str:
    """sdamgia lists every accepted permutation ("124|142|…") — keep one, sorted."""
    first = ans.split("|")[0]
    return "".join(sorted(re.sub(r"\D", "", first)))


def canon_word(ans: str) -> str:
    """Free-text ФИПИ answers: the word(s) run together, no spaces or case."""
    return re.sub(r"[^а-яё]", "", ans.lower().replace("ё", "е"))


def main() -> None:
    sd = json.loads((OUT / "ortho_sdamgia.json").read_text(encoding="utf-8"))
    fp = json.loads((OUT / "ortho_fipi.json").read_text(encoding="utf-8"))
    ans_path = OUT / "fipi_answers.json"
    fipi_answers: dict[str, str] = (
        json.loads(ans_path.read_text(encoding="utf-8")) if ans_path.exists() else {}
    )

    bank: list[dict] = []
    seen: set[tuple] = set()

    for t in sd:
        t = dict(t)
        t["answer"] = canon_answer(t["answer"])
        t.setdefault("answer_kind", "rows")
        if not t["answer"]:
            continue
        seen.add(row_key(t))
        bank.append(t)

    kept = dropped_dup = dropped_noans = 0
    for t in fp:
        key = row_key(t)
        if key in seen:
            dropped_dup += 1
            continue
        raw = fipi_answers.get(t["guid"], "")
        kind = t.get("answer_kind", "rows")
        answer = canon_answer(raw) if kind == "rows" else canon_word(raw)
        if not answer:
            dropped_noans += 1
            continue
        t = dict(t)
        t["answer"] = answer
        seen.add(key)
        bank.append(t)
        kept += 1

    by_no: dict[int, int] = {}
    for t in bank:
        by_no[t["task_no"]] = by_no.get(t["task_no"], 0) + 1
    print(
        f"[merge] {len(bank)} tasks — sdamgia {len(bank) - kept}, ФИПИ {kept} "
        f"(дубли {dropped_dup}, без ответа {dropped_noans})"
    )
    print("        " + ", ".join(f"№{k}={v}" for k, v in sorted(by_no.items())))
    path = OUT / "ortho.json"
    path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[write] {path}")


if __name__ == "__main__":
    main()
