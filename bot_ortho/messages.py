"""Bot message templates."""
from __future__ import annotations

import html

TOPICS = {
    9: "Правописание корней",
    10: "Правописание приставок",
    11: "Правописание суффиксов (кроме -Н-/-НН-)",
    12: "Личные окончания глаголов и суффиксы причастий",
}

GREETING = (
    "Привет! 👋\n\n"
    "Я тренажёр орфографии для ЕГЭ — задания <b>9–12</b>:\n"
    "• №9 — правописание корней\n"
    "• №10 — правописание приставок\n"
    "• №11 — правописание суффиксов\n"
    "• №12 — личные окончания глаголов и суффиксы причастий\n\n"
    "Показываю задание с пятью рядами слов — ты пишешь номера рядов, "
    "где пропущена одна и та же буква. Например: <code>124</code> "
    "(порядок и запятые не важны).\n\n"
    "Тему можно выбрать командой /topic. Жми «Поехали!» 🚀"
)

QUIT = "Ок, до встречи! Пиши /start, когда захочешь продолжить."

HELP = (
    "Команды:\n"
    "/start — начать заново\n"
    "/topic — выбрать тему (или все вперемешку)\n"
    "/stats — статистика\n\n"
    "Ответ — номера рядов: <code>124</code>, <code>1 2 4</code> или <code>1,2,4</code>."
)


def topic_name(task_no: int | None) -> str:
    return TOPICS.get(task_no, "Все темы вперемешку") if task_no else "Все темы вперемешку"


ASK = {
    "rows": "Напиши номера рядов.",
    "word": "Выпиши слово (или оба слова ряда), вставив пропущенную букву.",
}

NUDGE = {
    "rows": (
        "Жду номера рядов — например <code>124</code>. "
        "Если не знаешь — жми «Сдаюсь»."
    ),
    "word": (
        "Жду само слово с вставленной буквой — например <code>приуныть</code>. "
        "Если не знаешь — жми «Сдаюсь»."
    ),
}


def render_task(task: dict, seq: int | None = None) -> str:
    rows = "\n".join(
        f"<b>{n})</b> {html.escape(text)}"
        for n, text in sorted(task["rows"].items(), key=lambda kv: int(kv[0]))
    )
    head = f"<i>Задание {task['task_no']} — {html.escape(task['topic'])}</i>"
    hint = ASK[task.get("answer_kind", "rows")]
    return (
        f"{head}\n\n"
        f"{html.escape(task['prompt'])}\n\n"
        f"{rows}\n\n"
        f"{hint}"
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
        f"✅ <b>Верно!</b> Ответ: <b>{html.escape(task['answer'])}</b>.{bravo}"
        f"{_explanation(task)}"
    )


def render_wrong(task: dict, user_text: str) -> str:
    return (
        f"❌ <b>Не то.</b> Ты написала: <b>{html.escape(user_text.strip())}</b>, "
        f"правильный ответ: <b>{html.escape(task['answer'])}</b>."
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
