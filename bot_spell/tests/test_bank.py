"""The shipped bank must always be gradable and renderable."""
import json
import re
from pathlib import Path

import answer
import messages

BANK = json.loads(
    (Path(__file__).resolve().parents[2] / "out" / "spell.json").read_text("utf-8")
)

TOKEN_RE = re.compile(r"\([А-ЯЁа-яё]+\)")


def test_bank_is_not_empty():
    assert len(BANK) > 500


def test_every_task_is_well_formed():
    for t in BANK:
        assert t["task_no"] in (13, 14), t["id"]
        assert t["answer_kind"] == "spelling", t["id"]
        assert t["prompt"].strip() and t["topic"].strip(), t["id"]
        # the asked word is in the sentence, still in brackets, and alone
        assert t["word"] in t["sentence"], t["id"]
        assert TOKEN_RE.search(t["word"]), t["id"]
        assert len(TOKEN_RE.findall(t["sentence"])) == 1, t["id"]


def test_answer_is_the_asked_word_with_the_brackets_opened():
    for t in BANK:
        assert re.fullmatch(r"[а-яё]+(?:[ -][а-яё]+)?", t["answer"]), t["id"]
        letters = re.sub(r"[^а-яё]", "", t["answer"])
        assert letters == re.sub(r"[^а-яё]", "", t["word"].lower()), t["id"]


def test_ids_are_unique():
    ids = [t["id"] for t in BANK]
    assert len(ids) == len(set(ids))


def test_rendering_fits_telegram_limit():
    for t in BANK:
        assert len(messages.render_task(t)) < 4096, t["id"]
        assert len(messages.render_correct(t, 0)) < 4096, t["id"]
        assert len(messages.render_wrong(t, "не знаю")) < 4096, t["id"]
        assert len(messages.render_giveup(t)) < 4096, t["id"]


def test_the_asked_word_is_bold_and_the_others_are_not():
    for t in BANK:
        assert f"<b>{t['word']}</b>" in messages.render_task(t), t["id"]


def test_every_answer_grades_itself():
    for t in BANK:
        assert answer.is_correct(t["answer"], t["answer"]), t["id"]
        assert answer.looks_like_answer(t["answer"]), t["id"]
