#!/usr/bin/env python3
"""
Verify proposed answers for ФИПИ open-bank tasks.

The bank publishes no answer key: the only way to confirm an answer is the same
endpoint the site's own "Ответить" button uses (solve.php → 1/2/3, where 3 means
"верно"). So we solve each task ourselves and send exactly ONE request per task
to confirm it — no brute forcing.

  todo    — list the tasks that still need an answer   (out/fipi_todo.json)
  verify  — check out/fipi_proposed.json against ФИПИ, writing the confirmed
            ones to out/fipi_answers.json and reporting the rest

Usage:
    python3 solve_fipi.py todo
    python3 solve_fipi.py verify
"""
from __future__ import annotations

import json
import re
import sys
import time
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
PROJ = "AF0ED3F2557F8FFC4C06F80B6803FD26"
BANK_URL = f"https://ege.fipi.ru/bank/index.php?proj={PROJ}"
SOLVE_URL = "https://ege.fipi.ru/bank/solve.php"
DELAY = 1.5  # seconds between requests — one request per task, unhurried

TODO_PATH = OUT / "fipi_todo.json"
PROPOSED_PATH = OUT / "fipi_proposed.json"
ANSWERS_PATH = OUT / "fipi_answers.json"


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def curl(args: list[str]) -> str:
    out = subprocess.run(
        ["curl", "-sS", "-A", UA, "-H", f"Referer: {BANK_URL}", *args],
        check=True,
        capture_output=True,
    )
    return out.stdout.decode("cp1251", errors="replace")


def norm_row(s: str) -> str:
    s = s.lower().replace("ё", "е")
    s = re.sub(r"\([^)]*\)", "", s)
    return re.sub(r"[^а-я]", "", s)


def row_key(task: dict) -> tuple:
    return tuple(sorted(norm_row(v) for v in task["rows"].values()))


def cmd_todo() -> None:
    """Tasks with no answer yet and no sdamgia twin to borrow one from."""
    fipi = json.loads((OUT / "ortho_fipi.json").read_text(encoding="utf-8"))
    sd = json.loads((OUT / "ortho_sdamgia.json").read_text(encoding="utf-8"))
    known = {row_key(t) for t in sd}
    have = json.loads(ANSWERS_PATH.read_text(encoding="utf-8")) if ANSWERS_PATH.exists() else {}
    todo = [t for t in fipi if row_key(t) not in known and not have.get(t["guid"])]
    TODO_PATH.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[todo] {len(todo)} tasks need an answer → {TODO_PATH}")


def wire_answer(task: dict, proposed: str) -> str:
    """Convert our answer into the string the site's own form would submit."""
    if task["answer_kind"] == "rows":
        digits = set(re.findall(r"[1-5]", proposed))
        return "".join("1" if str(i + 1) in digits else "0" for i in range(len(task["rows"])))
    return proposed.strip()


def cmd_verify() -> None:
    tasks = {t["guid"]: t for t in json.loads(TODO_PATH.read_text(encoding="utf-8"))}
    proposed: dict[str, str] = json.loads(PROPOSED_PATH.read_text(encoding="utf-8"))
    confirmed: dict[str, str] = (
        json.loads(ANSWERS_PATH.read_text(encoding="utf-8")) if ANSWERS_PATH.exists() else {}
    )

    # ege.fipi.ru is signed by a Russian CA that macOS trusts but certifi does
    # not, so the requests go through curl, which uses the system trust store.
    cookie_jar = Path(tempfile.mkdtemp()) / "fipi.cookies"

    def new_session() -> None:
        """The checker hands out a short-lived session; re-open the bank page."""
        curl(["-c", str(cookie_jar), BANK_URL])
        curl(["-b", str(cookie_jar), "-c", str(cookie_jar),
              f"https://ege.fipi.ru/bank/questions.php?proj={PROJ}&page=0&pagesize=10"])

    new_session()

    wrong: list[str] = []
    for guid, ans in proposed.items():
        if guid in confirmed:
            continue
        task = tasks.get(guid)
        if task is None:
            print(f"  ?? {guid}: not in todo list, skipped")
            continue
        payload = urllib.parse.urlencode(
            {"guid": guid, "answer": wire_answer(task, ans), "ajax": "1", "proj": PROJ}
        )
        def ask() -> str:
            return curl(
                [
                    "-b", str(cookie_jar), "-c", str(cookie_jar),
                    "-X", "POST", "--data", payload, SOLVE_URL,
                ]
            ).strip()

        verdict = ask()
        if verdict not in ("1", "2", "3"):  # session expired — renew and retry once
            time.sleep(DELAY)
            new_session()
            time.sleep(DELAY)
            verdict = ask()
        if verdict == "3":
            confirmed[guid] = ans
        else:
            wrong.append(guid)
            print(f"  ✗ {task['id']} (№{task['task_no']}) proposed={ans!r} verdict={verdict}")
        time.sleep(DELAY)

    ANSWERS_PATH.write_text(json.dumps(confirmed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[verify] подтверждено {len(confirmed)}, не сошлось {len(wrong)}")
    if wrong:
        (OUT / "fipi_wrong.json").write_text(
            json.dumps(wrong, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"         список расхождений → {OUT / 'fipi_wrong.json'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "todo"
    {"todo": cmd_todo, "verify": cmd_verify}[cmd]()
