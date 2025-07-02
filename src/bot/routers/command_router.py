# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/command_router.py
"""
Командный роутер:
    • /start_operation  –сброс FSM, показ клавиатуры выбора даты.
    • /cancel_operation –сброс FSM и возврат к стартовой клавиатуре.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from src.bot.routers.date_type_router import _get_choose_operation_date_message
from src.bot.utils.legacy_messages import track_messages

from src.bot.keyboards.date_kb import create_date_kb
from src.bot.state.operation_state import OperationState, reset_state
from src.core.logger import configure_logger

__all__ = ["router"]

router = Router()
log = configure_logger(prefix="CMD", color="yellow", level="INFO")

# ---------- helpers --------------------------------------------------------- #


def _start_button_kb() -> ReplyKeyboardBuilder:
    """Возвращает клавиатуру с единственной кнопкой «Начать ввод операции»."""
    return (
        ReplyKeyboardBuilder()
        .add(KeyboardButton(text="Начать ввод операции"))
        .adjust(1)
    )


# ---------- /start_operation ------------------------------------------------ #


@router.message(Command("start_operation"))
@track_messages
async def cmd_start_operation(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Сбрасывает текущее состояние и предлагает пользователю выбрать дату
    новой операции.
    """
    await reset_state(state)

    iso_now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    await state.update_data(recording_date=iso_now, state_history=[])

    text, kb = await _get_choose_operation_date_message(state)
    cal_msg = await message.answer(text, reply_markup=kb)
    await state.update_data(date_message_id=cal_msg.message_id)          # ⬅️
    await state.set_state(OperationState.choosing_operation_date)


# ---------- /cancel_operation ---------------------------------------------- #


@router.message(Command("cancel_operation"))
@track_messages
async def cmd_cancel_operation(message: Message, state: FSMContext, bot: Bot) -> None:
    """Полный сброс FSM и возврат к стартовой кнопке."""
    await reset_state(state)

    await message.answer(
        "⛔ Операция отменена.",
        reply_markup=_start_button_kb().as_markup(resize_keyboard=True),
    )
    log.info("User %s cancelled an operation", message.from_user.id)