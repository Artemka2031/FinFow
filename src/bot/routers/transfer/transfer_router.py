# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/transfer/transfer_router.py
"""
Роутер для обработки операций типа «Перемещение».

Сценарий:
1. Пользователь выбирает исходный кошелёк → сообщение обновляется с подтверждением.
2. Бот отправляет новое сообщение со списком кошельков пополнения (без уже выбранного).
3. Пользователь выбирает целевой кошелёк → сообщение обновляется с подтверждением.
4. Бот запрашивает сумму перевода в новом сообщении.

Маршруты также переиспользуются навигацией «Назад», поэтому функции
`_get_choose_*_wallet_message` оставлены с теми же сигнатурами, что и прежде.
"""

from __future__ import annotations

from typing import Final, Union

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.wallet_kb import create_wallet_keyboard, WalletCallback
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_wallet


# ──────────────────────────── HELPERS ──────────────────────────────

def _to_markup(
        kb: Union[InlineKeyboardBuilder, InlineKeyboardMarkup]
) -> InlineKeyboardMarkup:
    """Приводит builder или готовую разметку к InlineKeyboardMarkup."""
    return kb.as_markup() if isinstance(kb, InlineKeyboardBuilder) else kb


router: Final = Router()
log = configure_logger(prefix="TRANSFER", color="magenta", level="INFO")


async def _get_choose_from_wallet_message(
        cb: CallbackQuery, state: FSMContext
) -> tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру выбора *исходного* кошелька."""
    async with get_async_session() as session:
        kb = await create_wallet_keyboard(session, state=state)
    return (
        "🟢 Выберите <b>кошелёк</b>, откуда произошло перемещение:",
        kb,
    )


async def _get_choose_to_wallet_message(
        cb: CallbackQuery, state: FSMContext
) -> tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру выбора *целевого* кошелька, исключая уже выбранный."""
    async with get_async_session() as session:
        data = await state.get_data()
        from_wallet = data.get("from_wallet")
        kb = await create_wallet_keyboard(session, state=state, exclude_wallet=from_wallet)
    return (
        "🔵 Выберите <b>кошелёк</b>, куда поступят деньги:",
        kb,
    )


def _get_enter_amount_message() -> str:
    """Текст запроса суммы перевода."""
    return "💰 Введите <b>сумму</b> перевода (в рублях):"


# ─────────────────────── CHOOSE FROM WALLET ────────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_from_wallet)
@track_messages
async def set_from_wallet(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        callback_data: WalletCallback,
) -> None:
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id
    await state.update_data(
        from_wallet=wallet_id,
        state_history=[OperationState.choosing_from_wallet.state],
    )
    log.info("User %s: from_wallet=%s", cb.from_user.id, wallet_id)

    # Обновляем текущее сообщение с подтверждением
    confirm_text = f"Выбран кошелёк, <b>откуда</b> произошло перемещение:\n✅  <b>{wallet_number}</b>"
    await cb.message.edit_text(confirm_text, reply_markup=None)

    # Отправляем новое сообщение с выбором целевого кошелька
    text, kb_builder = await _get_choose_to_wallet_message(cb, state)
    text = text.format(from_wallet=wallet_number)  # Используем wallet_number
    new_message = await bot.send_message(
        cb.message.chat.id, text, reply_markup=_to_markup(kb_builder)
    )
    await state.update_data(to_wallet_message_id=new_message.message_id)

    await state.set_state(OperationState.choosing_to_wallet)
    await cb.answer()


# ─────────────────────── CHOOSE TO WALLET ──────────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_to_wallet)
@track_messages
async def set_to_wallet(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        callback_data: WalletCallback,
) -> None:
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id
    await state.update_data(
        to_wallet=wallet_id,
        state_history=[OperationState.choosing_to_wallet.state],
    )
    log.info("User %s: to_wallet=%s", cb.from_user.id, wallet_id)

    # Обновляем текущее сообщение с подтверждением
    confirm_text = f"Выбран кошелёк, <b>куда</b> поступят деньги:\n✅ <b>{wallet_number}</b>"
    await cb.message.edit_text(confirm_text, reply_markup=None)

    # Запрашиваем сумму в новом сообщении
    amount_message = await bot.send_message(cb.message.chat.id, _get_enter_amount_message())
    await state.update_data(amount_message_id=amount_message.message_id)

    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()
