# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/contractor_kb.py
"""
Клавиатура для выбора Contractor из БД.

• Загружает всех подрядчиков через метод get_contractors.
• Строит InlineKeyboardMarkup с callback‑схемой CTR.
• Отображает все записи без пагинации (для отладки).
"""

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import get_contractors, Contractor


class ContractorCallback(CallbackData, prefix="CTR"):
    """CallbackData для выбора подрядчика."""
    contractor_id: int


async def create_contractor_keyboard(session: AsyncSession, state=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех подрядчиков.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    contractors = await get_contractors(session)  # type: List[Contractor]
    items: List[tuple[str, str, ContractorCallback]] = [
        (
            ctr.name,
            str(ctr.contractor_id),
            ContractorCallback(contractor_id=ctr.contractor_id),
        )
        for ctr in contractors
    ]

    # Авто‑раскладка: колонок столько, сколько помещается по длине текста
    return await build_inline_keyboard(items, state=state)