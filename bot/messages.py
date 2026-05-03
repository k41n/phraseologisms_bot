"""Bot message templates."""
from __future__ import annotations

import html

GREETING = (
    "Привет! 👋\n\n"
    "Я тренажёр для задания №25 ЕГЭ — там, где нужно <b>найти фразеологизм</b> "
    "в указанных предложениях.\n\n"
    "Я буду показывать тебе кусочек текста и вопрос. Твоя задача — выписать "
    "фразеологизм. Можно с пробелами или без — я разберусь.\n\n"
    "Жми «Поехали!» 🚀"
)

QUIT = "Ок, до встречи! Я никуда не денусь — пиши /start, когда захочешь продолжить."


def render_task(task: dict) -> str:
    ctx = html.escape(task["context"])
    q = html.escape(task["question"])
    src = html.escape(task["category"])
    return (
        f"<i>{src}</i>\n\n"
        f"<b>📖 Текст:</b>\n{ctx}\n\n"
        f"<b>❓ Задание:</b>\n{q}\n\n"
        f"Напиши ответ в чат."
    )


def render_correct(task: dict) -> str:
    expl = html.escape(task["explanation"])
    return (
        f"✅ <b>Верно!</b>\n\n"
        f"Ответ: <b>{html.escape(task['answer'])}</b>\n\n"
        f"<i>{expl}</i>"
    )


def render_wrong(task: dict, user_input: str) -> str:
    expl = html.escape(task["explanation"])
    return (
        f"❌ <b>Не угадала.</b> Ты написала: <i>«{html.escape(user_input)}»</i>\n\n"
        f"Правильный ответ: <b>{html.escape(task['answer'])}</b>\n\n"
        f"<i>{expl}</i>"
    )


def render_giveup(task: dict) -> str:
    expl = html.escape(task["explanation"])
    return (
        f"🤷 Без проблем. Ответ: <b>{html.escape(task['answer'])}</b>\n\n"
        f"<i>{expl}</i>"
    )


def render_stats(stats: dict, total_tasks: int) -> str:
    accuracy = stats["accuracy"] * 100
    return (
        f"📊 <b>Статистика</b>\n\n"
        f"Сделано подходов: <b>{stats['total_attempts']}</b>\n"
        f"Разных заданий: <b>{stats['unique_tasks']}</b> из {total_tasks}\n"
        f"Правильных: <b>{stats['correct']}</b>\n"
        f"Точность: <b>{accuracy:.0f}%</b>"
    )
