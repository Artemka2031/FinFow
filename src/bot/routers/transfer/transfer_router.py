# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/transfer/transfer_router.py
"""Роутер обработки операций типа «Перемещение».

Сценарий:
    1. Юзер выбирает *исходный* кошелёк — сообщение обновляется.
    2. Бот присылает список кошельков для пополнения (без уже выбранного).
    3. Юзер выбирает *целевой* кошелёк — сообщение обновляется.
    4. Бот запрашивает сумму перевода.

Функции `_get_choose_*_wallet_message` используются навигацией «Назад»,
поэтому их сигнатуры сохранены без изменений.
"""

from __future__ import annotations

from typing import Final, Tuple

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.wallet_kb import WalletCallback, create_wallet_keyboard
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_wallet

# ─────────────────────────── ТЕКСТОВЫЕ КОНСТАНТЫ ────────────────────────────
EMOJI_FROM:   Final = "🟢"
EMOJI_TO:     Final = "🔵"
EMOJI_AMOUNT: Final = "💰"

MSG_CHOOSE_FROM_WALLET: Final = (
    f"{EMOJI_FROM} Выберите <b>кошелёк</b>, откуда произошло перемещение:"
)
MSG_CHOOSE_TO_WALLET:   Final = (
    f"{EMOJI_TO} Выберите <b>кошелёк</b>, куда поступят деньги:"
)
MSG_ENTER_AMOUNT:       Final = (
    f"{EMOJI_AMOUNT} Введите <b>сумму</b> перевода (в рублях):"
)

MSG_CONFIRM_FROM_WALLET: Final = (
    "Выбран кошелёк, <b>откуда</b> произошло перемещение:\n"
    "✅  <b>{wallet_number}</b>"
)
MSG_CONFIRM_TO_WALLET: Final = (
    "Выбран кошелёк, <b>куда</b> поступят деньги:\n"
    "✅ <b>{wallet_number}</b>"
)

# ──────────────────────────── РОУТЕР И ЛОГГЕР ─────────────────────────────
router: Final = Router()
log = configure_logger(prefix="TRANSFER", color="magenta", level="INFO")

# ───────────────────── Формирование сообщений выбора ─────────────────────
async def _get_choose_from_wallet_message(
    cb: CallbackQuery,  # noqa: ARG001 (сигнатура сохранена для совместимости)
    state: FSMContext,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Текст и клавиатура для выбора *исходного* кошелька."""
    async with get_async_session() as session:
        kb = await create_wallet_keyboard(session, state=state)
    return MSG_CHOOSE_FROM_WALLET, kb


async def _get_choose_to_wallet_message(
    cb: CallbackQuery,  # noqa: ARG001
    state: FSMContext,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Текст и клавиатура для выбора *целевого* кошелька."""
    async with get_async_session() as session:
        data = await state.get_data()
        from_wallet = data.get("from_wallet")
        kb = await create_wallet_keyboard(
            session, state=state, exclude_wallet=from_wallet
        )
    return MSG_CHOOSE_TO_WALLET, kb


def _get_enter_amount_message() -> str:
    """Текст запроса суммы перевода."""
    return MSG_ENTER_AMOUNT


# ─────────────────────── ВЫБОР ИСХОДНОГО КОШЕЛЬКА ─────────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_from_wallet)
@track_messages
async def set_from_wallet(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: WalletCallback,  # noqa: ARG001
) -> None:
    """Сохраняет выбранный *исходный* кошелёк и переходит к выбору целевого."""
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id

    await state.update_data(
        from_wallet=wallet_id,
        state_history=[OperationState.choosing_from_wallet.state],
    )
    log.info(
        f"Юзер {cb.from_user.full_name}: выбран from_wallet – {wallet_id}, "
        f"кошелёк – {wallet_number}"
    )

    # Обновляем сообщение с подтверждением выбора исходного кошелька
    confirm_text = MSG_CONFIRM_FROM_WALLET.format(wallet_number=wallet_number)
    await cb.message.edit_text(confirm_text, reply_markup=None)

    # Запрашиваем выбор целевого кошелька
    text, kb = await _get_choose_to_wallet_message(cb, state)
    new_message = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
    await state.update_data(to_wallet_message_id=new_message.message_id)

    await state.set_state(OperationState.choosing_to_wallet)
    await cb.answer()


# ─────────────────────── ВЫБОР ЦЕЛЕВОГО КОШЕЛЬКА ─────────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_to_wallet)
@track_messages
async def set_to_wallet(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: WalletCallback,  # noqa: ARG001
) -> None:
    """Сохраняет выбранный *целевой* кошелёк и запрашивает сумму."""
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id

    await state.update_data(
        to_wallet=wallet_id,
        state_history=[OperationState.choosing_to_wallet.state],
    )
    log.info(
        f"Юзер {cb.from_user.full_name}: выбран to_wallet – {wallet_id}, "
        f"кошелёк – {wallet_number}"
    )

    # Обновляем сообщение с подтверждением выбора целевого кошелька
    confirm_text = MSG_CONFIRM_TO_WALLET.format(wallet_number=wallet_number)
    await cb.message.edit_text(confirm_text, reply_markup=None)

    # Запрашиваем сумму перевода
    amount_message = await bot.send_message(
        cb.message.chat.id, _get_enter_amount_message()
    )

    amoount_message_id = amount_message.message_id
    await state.update_data(amount_message_id=amoount_message_id)

    log.warning(f"amount_message_id={amoount_message_id}")

    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()

# ─────────────────────────────────────────────────────────────────────────
