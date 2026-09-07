"""Orthography trainer (ЕГЭ №9–12) Telegram bot — entry point."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

import answer
import messages
import storage

logger = logging.getLogger("ortho-bot")

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ORTHO_DATA = (ROOT / os.environ.get("ORTHO_DATA", "../out/ortho.json")).resolve()
PROGRESS_DB = (ROOT / os.environ.get("PROGRESS_DB", "./progress.sqlite3")).resolve()


class TrainerState(StatesGroup):
    waiting_answer = State()


# -------------------------------------------------------------------- data


def load_tasks() -> dict[str, dict]:
    raw = json.loads(ORTHO_DATA.read_text(encoding="utf-8"))
    return {t["id"]: t for t in raw}


TASKS: dict[str, dict] = load_tasks()
PROGRESS = storage.Storage(PROGRESS_DB)


def task_ids_for(task_no: int | None) -> list[str]:
    if task_no is None:
        return list(TASKS)
    return [tid for tid, t in TASKS.items() if t["task_no"] == task_no]


# -------------------------------------------------------------------- ui


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Поехали!", callback_data="next")],
            [InlineKeyboardButton(text="🎯 Выбрать тему", callback_data="topic")],
        ]
    )


def kb_during_task() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤷 Сдаюсь", callback_data="giveup"),
                InlineKeyboardButton(text="⏹ Стоп", callback_data="quit"),
            ]
        ]
    )


def kb_after_task() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶ Следующее", callback_data="next")],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
                InlineKeyboardButton(text="🎯 Тема", callback_data="topic"),
                InlineKeyboardButton(text="⏹ Стоп", callback_data="quit"),
            ],
        ]
    )


def kb_topics(current: int | None) -> InlineKeyboardMarkup:
    def label(no: int | None, text: str) -> str:
        return ("✅ " if no == current else "") + text

    rows = [[InlineKeyboardButton(text=label(None, "Все вперемешку"), callback_data="topic:all")]]
    for no, name in messages.TOPICS.items():
        rows.append(
            [InlineKeyboardButton(text=label(no, f"№{no} — {name}"), callback_data=f"topic:{no}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# -------------------------------------------------------------------- helpers


async def deliver_next_task(target: Message, state: FSMContext, user_id: int) -> None:
    task_no = PROGRESS.topic(user_id)
    ids = task_ids_for(task_no)
    next_id = PROGRESS.pick_next(user_id, ids)
    if next_id is None:
        await target.answer("По этой теме заданий нет. Попробуй /topic.")
        return
    await state.set_state(TrainerState.waiting_answer)
    await state.update_data(current_task_id=next_id)
    await target.answer(messages.render_task(TASKS[next_id]), reply_markup=kb_during_task())


async def finish_task(
    target: Message, state: FSMContext, user_id: int, task: dict, correct: bool, text: str | None
) -> None:
    PROGRESS.record_attempt(user_id, task["id"], task["task_no"], correct)
    await state.set_state(None)
    if correct:
        streak = PROGRESS.stats(user_id)["streak"]
        body = messages.render_correct(task, streak)
    elif text is None:
        body = messages.render_giveup(task)
    else:
        body = messages.render_wrong(task, text)
    await target.answer(body, reply_markup=kb_after_task())


# -------------------------------------------------------------------- handlers


dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def on_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(messages.GREETING, reply_markup=kb_start())


@dp.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(messages.HELP)


@dp.message(Command("topic"))
async def on_topic_command(message: Message) -> None:
    current = PROGRESS.topic(message.from_user.id)
    await message.answer("Что тренируем?", reply_markup=kb_topics(current))


@dp.message(Command("stats"))
async def on_stats_command(message: Message) -> None:
    uid = message.from_user.id
    task_no = PROGRESS.topic(uid)
    await message.answer(
        messages.render_stats(PROGRESS.stats(uid), len(task_ids_for(task_no)), task_no)
    )


@dp.callback_query(F.data == "next")
async def on_next(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await deliver_next_task(query.message, state, query.from_user.id)


@dp.callback_query(F.data == "topic")
async def on_topic_button(query: CallbackQuery) -> None:
    await query.answer()
    await query.message.answer(
        "Что тренируем?", reply_markup=kb_topics(PROGRESS.topic(query.from_user.id))
    )


@dp.callback_query(F.data.startswith("topic:"))
async def on_topic_choice(query: CallbackQuery, state: FSMContext) -> None:
    raw = query.data.split(":", 1)[1]
    task_no = None if raw == "all" else int(raw)
    PROGRESS.set_topic(query.from_user.id, task_no)
    await query.answer("Тема выбрана")
    await state.set_state(None)
    await query.message.answer(
        f"Тема: <b>{messages.topic_name(task_no)}</b> "
        f"({len(task_ids_for(task_no))} заданий).",
        reply_markup=kb_after_task(),
    )


@dp.callback_query(F.data == "stats")
async def on_stats_button(query: CallbackQuery) -> None:
    uid = query.from_user.id
    task_no = PROGRESS.topic(uid)
    await query.answer()
    await query.message.answer(
        messages.render_stats(PROGRESS.stats(uid), len(task_ids_for(task_no)), task_no),
        reply_markup=kb_after_task(),
    )


@dp.callback_query(F.data == "quit")
async def on_quit(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer()
    await query.message.answer(messages.QUIT)


@dp.callback_query(F.data == "giveup", TrainerState.waiting_answer)
async def on_giveup(query: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = data.get("current_task_id")
    if task_id is None:
        await query.answer("Нет текущего задания.")
        return
    await query.answer()
    await finish_task(query.message, state, query.from_user.id, TASKS[task_id], False, None)


@dp.message(TrainerState.waiting_answer, F.text)
async def on_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = data.get("current_task_id")
    if task_id is None:
        await state.clear()
        await message.answer("Что-то я потерял задание. /start — начнём заново.")
        return
    task = TASKS[task_id]
    kind = task.get("answer_kind", "rows")
    if not answer.looks_like_answer(message.text, kind):
        await message.answer(messages.NUDGE[kind])
        return
    correct = answer.is_correct(message.text, task["answer"], kind)
    await finish_task(message, state, message.from_user.id, task, correct, message.text)


@dp.message(F.text)
async def on_unsolicited_text(message: Message) -> None:
    await message.answer("Сейчас я ничего не жду. /start — начнём, /help — что я умею.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("loaded %d tasks; progress db: %s", len(TASKS), PROGRESS_DB)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
