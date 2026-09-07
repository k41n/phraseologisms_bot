"""The shipped bank must always be gradable and renderable."""
import json
import re
from pathlib import Path

import answer
import messages

BANK = json.loads((Path(__file__).resolve().parents[2] / "out" / "ortho.json").read_text("utf-8"))


def test_bank_is_not_empty():
    assert len(BANK) > 700


def test_every_task_has_answer_rows_and_topic():
    for t in BANK:
        assert t["task_no"] in (9, 10, 11, 12), t["id"]
        assert t["answer_kind"] in ("rows", "word"), t["id"]
        if t["answer_kind"] == "rows":
            assert re.fullmatch(r"[1-5]+", t["answer"]), t["id"]
            assert t["answer"] == "".join(sorted(set(t["answer"]))), t["id"]
        else:
            assert re.fullmatch(r"[а-я]+", t["answer"]), t["id"]
        assert 4 <= len(t["rows"]) <= 5, t["id"]
        assert all(v.strip() for v in t["rows"].values()), t["id"]
        assert t["prompt"].strip(), t["id"]


def test_ids_are_unique():
    ids = [t["id"] for t in BANK]
    assert len(ids) == len(set(ids))


def test_rendering_fits_telegram_limit():
    for t in BANK:
        assert len(messages.render_task(t)) < 4096, t["id"]
        assert len(messages.render_correct(t, 0)) < 4096, t["id"]
        assert len(messages.render_wrong(t, "124")) < 4096, t["id"]


def test_every_answer_grades_itself():
    for t in BANK:
        assert answer.is_correct(t["answer"], t["answer"], t["answer_kind"]), t["id"]
        assert answer.looks_like_answer(t["answer"], t["answer_kind"]), t["id"]
