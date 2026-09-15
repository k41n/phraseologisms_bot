"""Bot message templates."""
from __future__ import annotations

import html

TOPICS = {
    13: "Правописание НЕ и НИ",
    14: "Слитное, дефисное, раздельное написание",
}

GREETING = (
    "Привет! 👋\n\n"
    "Я тренажёр слитного, дефисного и раздельного написания — задания "
    "<b>13</b> и <b>14</b>:\n"
    "• №13 — НЕ и НИ\n"
    "• №14 — всё остальное: ТАКЖЕ и ТАК ЖЕ, ПО-ПРЕЖНЕМУ, В ТЕЧЕНИЕ…\n\n"
    "На экзамене дают пять предложений и просят выбрать номера. Я показываю "
    "по одному предложению: раскрой скобки и напиши, как пишется выделенное "
    "слово именно здесь. Например для "
    "<i>лежать (НЕ)ДВИГАЯСЬ</i> ответ: <code>не двигаясь</code>.\n\n"
    "Тему можно выбрать командой /topic. Жми «Поехали!» 🚀"
)

QUIT = "Ок, до встречи! Пиши /start, когда захочешь продолжить."

HELP = (
    "Команды:\n"
    "/start — начать заново\n"
    "/topic — выбрать тему (или обе вперемешку)\n"
    "/stats — статистика\n\n"
    "Ответ — само слово с раскрытыми скобками: <code>неизвестному</code>, "
    "<code>не двигаясь</code>, <code>давным-давно</code>. "
    "Регистр не важен, Ё можно писать как Е."
)

ASK = "Как пишется выделенное слово? Напиши его целиком."

NUDGE = (
    "Жду само слово с раскрытыми скобками — например <code>не двигаясь</code> "
    "или <code>по-прежнему</code>. Если не знаешь — жми «Сдаюсь»."
)


def topic_name(task_no: int | None) -> str:
    return TOPICS.get(task_no, "Обе темы вперемешку") if task_no else "Обе темы вперемешку"


def _highlight(sentence: str, word: str) -> str:
    """Bold the word in brackets — the one this task is about."""
    at = sentence.find(word)
    if at < 0:
        return html.escape(sentence)
    return (
        html.escape(sentence[:at])
        + f"<b>{html.escape(word)}</b>"
        + html.escape(sentence[at + len(word):])
    )


def render_task(task: dict) -> str:
    return (
        f"<i>Задание {task['task_no']} — {html.escape(task['topic'])}</i>\n\n"
        f"{_highlight(task['sentence'], task['word'])}\n\n"
        f"{ASK}"
    )


def _explanation(task: dict, limit: int = 2500) -> str:
    expl = (task.get("explanation") or "").strip()
    if not expl:
        return ""
    if len(expl) > limit:
        expl = expl[:limit].rsplit(" ", 1)[0] + "…"
    return f"\n\n<i>{html.escape(expl)}</i>"


def render_correct(task: dict, streak: int) -> str:
    bravo = f" Серия: {streak} подряд 🔥" if streak >= 3 else ""
    return (
        f"✅ <b>Верно!</b> Пишется <b>{html.escape(task['answer'])}</b>.{bravo}"
        f"{_explanation(task)}"
    )


def render_wrong(task: dict, user_text: str) -> str:
    return (
        f"❌ <b>Не то.</b> Ты написала: <b>{html.escape(user_text.strip())}</b>, "
        f"а пишется <b>{html.escape(task['answer'])}</b>."
        f"{_explanation(task)}"
    )


def render_giveup(task: dict) -> str:
    return (
        f"🤷 Правильный ответ: <b>{html.escape(task['answer'])}</b>."
        f"{_explanation(task)}"
    )


def render_stats(stats: dict, bank_size: int, task_no: int | None) -> str:
    if not stats["total_attempts"]:
        return "Пока ни одного ответа. Жми /start и поехали!"
    lines = [
        "📊 <b>Статистика</b>",
        f"Тема: {html.escape(topic_name(task_no))}",
        f"Всего ответов: {stats['total_attempts']}",
        f"Правильных: {stats['correct']} ({stats['accuracy'] * 100:.0f}%)",
        f"Разных заданий пройдено: {stats['unique_tasks']} из {bank_size}",
    ]
    if stats["streak"] >= 2:
        lines.append(f"Серия без ошибок: {stats['streak']} 🔥")
    if stats["per_topic"]:
        lines.append("")
        lines.append("<b>По темам:</b>")
        for row in stats["per_topic"]:
            pct = row["correct"] / row["total"] * 100 if row["total"] else 0
            lines.append(
                f"№{row['task_no']} {html.escape(TOPICS.get(row['task_no'], ''))}: "
                f"{row['correct']}/{row['total']} ({pct:.0f}%)"
            )
    return "\n".join(lines)
