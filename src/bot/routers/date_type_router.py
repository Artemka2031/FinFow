# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/date_type_router.py
"""
Мастер ввода операции:
  ▸ /start_operation ──┐
  ▸ «Начать ввод …»    ├─▶ 1) recording_date (ISO‑UTC, авто)
                       │
                       ├─▶ 2) выбор ДАТЫ операции  (inline‑календарь)
                       │
                       └─▶ 3) выбор ТИПА операции
                               ├─ Поступление → выбор кошелька для прихода
                               ├─ Перемещение → выбор кошелька‑источника
                               └─ Выбытие     → передача в outcome_router
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.calendar import create_date_kb
from src.bot.keyboards.calendar.custom_calendar import (
    CustomCalendar,
    CustomCalendarCallback,
)
from src.bot.keyboards.calendar.schemas import CustomCalAct
from src.bot.keyboards.wallet_kb import create_wallet_keyboard
from src.bot.routers.outcome.outcome_router import _show_dict_kb, _get_choose_outcome_source_message
from src.bot.routers.transfer.transfer_router import _get_choose_from_wallet_message
from src.bot.state import OperationState, reset_state
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger

router: Final = Router()
log = configure_logger(prefix="DATE/TYPE", color="cyan", level="INFO")

# ──────────────────────────── HELPERS ──────────────────────────────
MSG_CHOOSE_OP_DATE = "📅 Выберите <b>дату операции</b>:"
MSG_CONFIRM_OP_DATE = "📅 Выбранная <b>дата операции</b>: {}"
MSG_CHOOSE_OP_TYPE = "Выберите <b>тип операции</b>:"


def _op_type_kb() -> InlineKeyboardBuilder:
    """Клавиатура выбора типа операции."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🟢 Приход", callback_data="operation_type:Поступление"),
        InlineKeyboardButton(text="🔄 Перемещение", callback_data="operation_type:Перемещение"),
        InlineKeyboardButton(text="🔴 Выбытие", callback_data="operation_type:Выбытие"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def _get_choose_operation_date_message(state: FSMContext) -> tuple[str, InlineKeyboardMarkup]:
    kb = await create_date_kb()
    return MSG_CHOOSE_OP_DATE, kb


async def _get_choose_operation_type_message() -> tuple[str, InlineKeyboardBuilder]:
    return MSG_CHOOSE_OP_TYPE, _op_type_kb()



# ─────────────────────── START OPERATION ───────────────────────────
@router.message((F.text.lower() == "начать ввод операции") or Command("start_operation"))
@track_messages
async def start_operation(msg: Message, state: FSMContext, bot: Bot) -> None:
    await reset_state(state)

    iso_now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    await state.update_data(recording_date=iso_now, state_history=[])

    text, kb = await _get_choose_operation_date_message(state)
    cal_msg = await msg.answer(text, reply_markup=kb)
    await state.update_data(date_message_id=cal_msg.message_id)
    await state.set_state(OperationState.choosing_operation_date)


# ─────────────────────── CHOOSE OPERATION DATE ─────────────────────
@router.callback_query(F.data.startswith("custom_calendar"), OperationState.choosing_operation_date)
@track_messages
async def choose_op_date(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cal = CustomCalendar(locale="ru")
    data = CustomCalendarCallback.unpack(cb.data)

    if data.act in (CustomCalAct.today, CustomCalAct.yesterday):
        delta = 0 if data.act == CustomCalAct.today else 1
        selected = datetime.now() - timedelta(days=delta)
        ok, date_obj = True, selected
    else:
        ok, date_obj = await cal.process_selection(cb, data)

    if ok and date_obj:
        op_date = date_obj.strftime("%d.%m.%Y")
        await state.update_data(operation_date=op_date, state_history=[OperationState.choosing_operation_date.state])

        confirm_text = MSG_CONFIRM_OP_DATE.format(op_date)
        await cb.message.edit_text(confirm_text, reply_markup=None)

        text, kb = await _get_choose_operation_type_message()
        type_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
        await state.update_data(type_message_id=type_msg.message_id)
        await state.set_state(OperationState.choosing_operation_type)

    await cb.answer()


# ─────────────────────── CHOOSE OPERATION TYPE ─────────────────────
@router.callback_query(F.data.startswith("operation_type"), OperationState.choosing_operation_type)
@track_messages
async def set_operation_type(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    op_type = cb.data.split(":", 1)[1]
    await state.update_data(operation_type=op_type, state_history=[OperationState.choosing_operation_type.state])
    log.info(f"User {cb.from_user.id}: operation_type={op_type}")

    if op_type == "Поступление":
        text, kb = await _show_dict_kb(cb, state, create_wallet_keyboard, OperationState.choosing_income_wallet)
        text = "🟢 Выберите <b>кошелёк для поступления</b>:"
    elif op_type == "Перемещение":
        text, kb = await _get_choose_from_wallet_message(cb, state)
        await state.set_state(OperationState.choosing_from_wallet)
    elif op_type == "Выбытие":
        text, kb = await _get_choose_outcome_source_message()
        await state.set_state(OperationState.choosing_outcome_wallet_or_creditor)
    else:
        raise ValueError(f"Unknown operation_type: {op_type}")


    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
