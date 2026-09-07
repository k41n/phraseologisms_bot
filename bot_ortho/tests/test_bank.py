"""The shipped bank must always be gradable and renderable."""
import json
import re
from pathlib import Path

import answer
import messages

BANK = json.loads(
    (Path(__file__).resolve().parents[2] / "out" / "ortho_rows.json").read_text("utf-8")
)


def test_bank_is_not_empty():
    assert len(BANK) > 2000


def test_every_task_has_answer_and_topic():
    for t in BANK:
        assert t["task_no"] in (9, 10, 11, 12), t["id"]
        assert t["answer_kind"] in ("letters", "word"), t["id"]
        assert t["prompt"].strip(), t["id"]
        if t["answer_kind"] == "letters":
            assert re.fullmatch(r"[а-яё](, [а-яё])+", t["answer"]), t["id"]
            assert len(t["words"]) == len(t["answer"].split(", ")), t["id"]
            assert t["row"] == ", ".join(t["words"]), t["id"]
            assert all(w.count("..") == 1 for w in t["words"]), t["id"]
        else:
            assert re.fullmatch(r"[а-я]+", t["answer"]), t["id"]
            assert 4 <= len(t["rows"]) <= 5, t["id"]


def test_letters_agree_with_the_original_key():
    """All letters equal iff the row was one of the answers of the parent task."""
    parents = {
        t["id"]: t
        for t in json.loads(
            (Path(__file__).resolve().parents[2] / "out" / "ortho.json").read_text("utf-8")
        )
    }
    for t in BANK:
        if t["answer_kind"] != "letters":
            continue
        parent_id, _, no = t["id"].partition("#")
        letters = t["answer"].split(", ")
        assert (len(set(letters)) == 1) == (no in parents[parent_id]["answer"]), t["id"]


def test_ids_are_unique():
    ids = [t["id"] for t in BANK]
    assert len(ids) == len(set(ids))


def test_rendering_fits_telegram_limit():
    for t in BANK:
        assert len(messages.render_task(t)) < 4096, t["id"]
        assert len(messages.render_correct(t, 0)) < 4096, t["id"]
        assert len(messages.render_wrong(t, "и, и, и")) < 4096, t["id"]


def test_every_answer_grades_itself():
    for t in BANK:
        assert answer.is_correct(t["answer"], t["answer"], t["answer_kind"]), t["id"]
        assert answer.looks_like_answer(t["answer"], t["answer_kind"]), t["id"]
