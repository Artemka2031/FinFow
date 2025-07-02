# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/start_router.py
"""
Старт‑роутер:
    • реагирует на /start;
    • показывает краткое описание проекта и ссылку на документацию;
    • выводит Reply‑клавиатуру с одной кнопкой «Начать ввод операции».
"""

from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from src.bot.utils.legacy_messages import track_messages

from src.core.logger import configure_logger

__all__ = ["router"]

router = Router()
log = configure_logger(prefix="START", color="blue", level="INFO")

_PROJECT_DESCRIPTION = (
    "FinFlow — инструмент для управления финансовыми операциями: "
    "фиксируйте приходы, переводы и выбытия, привязывайте их к проектам "
    "и категориям и получайте удобную аналитику."
)
_PROJECT_DOCS = "https://finflow-docs.example.com"


@router.message(Command("start"))
@track_messages
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    """Приветствие + кнопка «Начать ввод операции»."""
    log.info("User %s issued /start", message.from_user.id)

    kb = (
        ReplyKeyboardBuilder()
        .add(KeyboardButton(text="Начать ввод операции"))
        .adjust(1)  # одна колонка
        .as_markup(resize_keyboard=True)
    )

    await message.answer(
        f"<b>Добро пожаловать в FinFlow!</b>\n\n"
        f"{_PROJECT_DESCRIPTION}\n\n"
        f"📖 <a href='{_PROJECT_DOCS}'>Документация проекта</a>",
        reply_markup=kb,
    )