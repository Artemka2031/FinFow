# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/date_type_router.py
"""Мастер ввода операции (шаги: дата → тип → кошельки/контрагенты).

Команды запуска:
    ▸ /start_operation
    ▸ «Начать ввод …»

Порядок действий:
    1) *recording_date*  — ISO‑UTC, фиксируется автоматически.
    2) Выбор даты         — inline‑календарь.
    3) Выбор типа         — Поступление / Перемещение / Выбытие.
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
from src.bot.routers.outcome.outcome_router import (
    _dict_kb, MSG_INDICATE_SOURCE, _kb_source,
)
from src.bot.routers.transfer.transfer_router import _get_choose_from_wallet_message
from src.bot.state import OperationState, reset_state
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger

# ─────────────────────────── ТЕКСТОВЫЕ КОНСТАНТЫ UI ────────────────────────────
EMOJI_CALENDAR: Final = "📅"
EMOJI_INCOME:   Final = "🟢"
EMOJI_TRANSFER: Final = "🔄"
EMOJI_OUTCOME:  Final = "🔴"

MSG_CHOOSE_OP_DATE:   Final = f"{EMOJI_CALENDAR} Выберите <b>дату операции</b>:"
MSG_CONFIRM_OP_DATE:  Final = f"{EMOJI_CALENDAR} Выбранная <b>дата операции</b>: {{}}"
MSG_CHOOSE_OP_TYPE:   Final = "Выберите <b>тип операции</b>:"

# ────────────────────────────── РОУТЕР И ЛОГГЕР ───────────────────────────────
router: Final = Router()
log = configure_logger(prefix="DATE/TYPE", color="cyan", level="INFO")

# ──────────────────────────────── ПОМОЩНИКИ ───────────────────────────────────

def _op_type_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа операции."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=f"{EMOJI_INCOME} Приход", callback_data="operation_type:Поступление"),
        InlineKeyboardButton(text=f"{EMOJI_TRANSFER} Перемещение", callback_data="operation_type:Перемещение"),
        InlineKeyboardButton(text=f"{EMOJI_OUTCOME} Выбытие", callback_data="operation_type:Выбытие"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def _get_choose_operation_date_message(state: FSMContext) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру для выбора даты операции."""
    kb = await create_date_kb()
    return MSG_CHOOSE_OP_DATE, kb


async def _get_choose_operation_type_message() -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст и клавиатуру для выбора типа операции."""
    return MSG_CHOOSE_OP_TYPE, _op_type_kb()

# ──────────────────────────── ЗАПУСК МАСТЕРА ──────────────────────────────────
@router.message((F.text.lower() == "начать ввод операции") or Command("start_operation"))
@track_messages
async def start_operation(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Старт мастера ввода операции."""
    await reset_state(state)

    iso_now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    await state.update_data(recording_date=iso_now, state_history=[])

    log.info(f"Юзер {msg.from_user.full_name}: started operation input wizard")

    text, kb = await _get_choose_operation_date_message(state)
    cal_msg = await msg.answer(text, reply_markup=kb)
    await state.update_data(date_message_id=cal_msg.message_id)
    await state.set_state(OperationState.choosing_operation_date)

# ─────────────────────────── ВЫБОР ДАТЫ ОПЕРАЦИИ ──────────────────────────────
@router.callback_query(F.data.startswith("custom_calendar"), OperationState.choosing_operation_date)
@track_messages
async def choose_op_date(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выбор даты операции пользователем."""
    cal = CustomCalendar(locale="ru_RU.UTF-8")
    data = CustomCalendarCallback.unpack(cb.data)

    if data.act in (CustomCalAct.today, CustomCalAct.yesterday):
        delta = 0 if data.act == CustomCalAct.today else 1
        selected = datetime.now() - timedelta(days=delta)
        ok, date_obj = True, selected
    else:
        ok, date_obj = await cal.process_selection(cb, data)

    if ok and date_obj:
        op_date = date_obj.strftime("%d.%m.%Y")
        await state.update_data(
            operation_date=op_date,
            state_history=[OperationState.choosing_operation_date.state],
        )

        log.info(f"Юзер {cb.from_user.full_name}: выбрана дата операции – {op_date}")

        confirm_text = MSG_CONFIRM_OP_DATE.format(op_date)
        await cb.message.edit_text(confirm_text, reply_markup=None)

        text, kb = await _get_choose_operation_type_message()
        type_msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
        await state.update_data(type_message_id=type_msg.message_id)
        await state.set_state(OperationState.choosing_operation_type)

    await cb.answer()

# ─────────────────────────── ВЫБОР ТИПА ОПЕРАЦИИ ──────────────────────────────
@router.callback_query(F.data.startswith("operation_type"), OperationState.choosing_operation_type)
@track_messages
async def set_operation_type(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Выбор типа операции (Поступление / Перемещение / Выбытие)."""
    op_type = cb.data.split(":", 1)[1]
    await state.update_data(
        operation_type=op_type,
        state_history=[OperationState.choosing_operation_type.state],
    )

    log.info(f"Юзер {cb.from_user.full_name}: выбран тип операции – {op_type}")

    if op_type == "Поступление":
        text, kb = await _dict_kb(state, create_wallet_keyboard, OperationState.choosing_income_wallet)
        text = f"{EMOJI_INCOME} Выберите <b>кошелёк для поступления</b>:"
    elif op_type == "Перемещение":
        text, kb = await _get_choose_from_wallet_message(cb, state)
        await state.set_state(OperationState.choosing_from_wallet)
    elif op_type == "Выбытие":
        text, kb = MSG_INDICATE_SOURCE, _kb_source()
        await state.set_state(OperationState.choosing_outcome_wallet_or_creditor)
    else:
        raise ValueError(f"Неизвестный тип операции: {op_type}")

    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ─────────────────────────────────────────────────────────────────────────────