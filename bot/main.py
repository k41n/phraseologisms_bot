"""Phraseology trainer Telegram bot — entry point."""
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
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from dotenv import load_dotenv

import answer
import messages
import storage

logger = logging.getLogger("phraseo-bot")

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.environ["BOT_TOKEN"]
PHRASEO_DATA = (ROOT / os.environ.get("PHRASEO_DATA", "../out/phraseo.json")).resolve()
PROGRESS_DB = (ROOT / os.environ.get("PROGRESS_DB", "./progress.sqlite3")).resolve()


# -------------------------------------------------------------------- state


class TrainerState(StatesGroup):
    waiting_answer = State()


# -------------------------------------------------------------------- data


def load_tasks() -> dict[int, dict]:
    raw = json.loads(PHRASEO_DATA.read_text(encoding="utf-8"))
    return {t["id"]: t for t in raw}


TASKS: dict[int, dict] = load_tasks()
TASK_IDS: list[int] = list(TASKS.keys())
PROGRESS = storage.Storage(PROGRESS_DB)


# -------------------------------------------------------------------- ui


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Поехали!", callback_data="next")]]
    )


def kb_during_task() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤷 Сдаюсь", callback_data="giveup"),
                InlineKeyboardButton(text="⏹ Стоп", callback_data="quit"),
            ],
        ]
    )


def kb_after_task() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶ Следующее", callback_data="next")],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
                InlineKeyboardButton(text="⏹ Стоп", callback_data="quit"),
            ],
        ]
    )


# -------------------------------------------------------------------- helpers


async def deliver_next_task(target: Message, state: FSMContext, user_id: int) -> None:
    next_id = PROGRESS.pick_next(user_id, TASK_IDS)
    if next_id is None:
        await target.answer("Заданий нет. Странно. Попробуй позже.")
        return
    task = TASKS[next_id]
    await state.set_state(TrainerState.waiting_answer)
    await state.update_data(current_task_id=next_id)
    await target.answer(messages.render_task(task), reply_markup=kb_during_task())


# -------------------------------------------------------------------- handlers


dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def on_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(messages.GREETING, reply_markup=kb_start())


@dp.message(Command("stats"))
async def on_stats_command(message: Message) -> None:
    s = PROGRESS.stats(message.from_user.id)
    await message.answer(messages.render_stats(s, len(TASK_IDS)))


@dp.callback_query(F.data == "next")
async def on_next(query: CallbackQuery, state: FSMContext) -> None:
    await query.answer()
    await deliver_next_task(query.message, state, query.from_user.id)


@dp.callback_query(F.data == "stats")
async def on_stats_button(query: CallbackQuery) -> None:
    s = PROGRESS.stats(query.from_user.id)
    await query.answer()
    await query.message.answer(
        messages.render_stats(s, len(TASK_IDS)), reply_markup=kb_after_task()
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
    task = TASKS[task_id]
    PROGRESS.record_attempt(query.from_user.id, task_id, correct=False)
    await state.set_state(None)
    await query.answer()
    await query.message.answer(messages.render_giveup(task), reply_markup=kb_after_task())


@dp.message(TrainerState.waiting_answer, F.text)
async def on_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    task_id = data.get("current_task_id")
    if task_id is None:
        await message.answer("Что-то я потерял задание. /start — начнём заново.")
        await state.clear()
        return
    task = TASKS[task_id]
    correct = answer.is_correct(message.text, task["answer_compact"])
    PROGRESS.record_attempt(message.from_user.id, task_id, correct=correct)
    await state.set_state(None)
    if correct:
        await message.answer(messages.render_correct(task), reply_markup=kb_after_task())
    else:
        await message.answer(
            messages.render_wrong(task, message.text), reply_markup=kb_after_task()
        )


@dp.message(F.text)
async def on_unsolicited_text(message: Message) -> None:
    await message.answer("Сейчас я ничего не жду. /start — начнём.")


# -------------------------------------------------------------------- main


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("loaded %d tasks; progress db: %s", len(TASK_IDS), PROGRESS_DB)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
