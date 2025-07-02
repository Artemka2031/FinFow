# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/wallet_kb.py
"""
Клавиатура для выбора Wallet из БД.

• Загружает все кошельки через метод get_wallets.
• Строит InlineKeyboardMarkup с callback‑схемой WAL.
• Для отладки выводит все записи без пагинации.
"""

from typing import List, Tuple

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.db import get_wallets, Wallet


class WalletCallback(CallbackData, prefix="WAL"):
    """CallbackData для выбора кошелька."""
    wallet_id: str


async def create_wallet_keyboard(session: AsyncSession, state=None, exclude_wallet=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех кошельков.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).
        exclude_wallet: id кошелька, который не должен отображаться

    Returns:
        InlineKeyboardMarkup с кнопками вида [<wallet_number>].
    """
    wallets = await get_wallets(session)  # type: List[Wallet]

    if exclude_wallet:
        wallets = [w for w in wallets if w.wallet_id != exclude_wallet]

    # Формируем кортежи (текст, raw_callback_data, CallbackData)
    items: List[Tuple[str, str, WalletCallback]] = [
        (
            w.wallet_number,
            w.wallet_id,
            WalletCallback(wallet_id=w.wallet_id),
        )
        for w in wallets
    ]

    return await build_inline_keyboard(items, state=state)
