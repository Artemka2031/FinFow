# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/founder_kb.py
"""
Клавиатура для выбора учредителя (Founder) из БД.

• Загружает всех учредителей через метод get_founders.
• Строит InlineKeyboardMarkup с callback‑схемой FDR.
• Отображает все записи (без пагинации) для отладки.
"""

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import get_founders, Founder


class FounderCallback(CallbackData, prefix="FDR"):
    """CallbackData для выбора учредителя."""
    founder_id: int


async def create_founder_keyboard(session: AsyncSession, state=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех учредителей.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    founders = await get_founders(session)  # type: List[Founder]
    items: List[tuple[str, str, FounderCallback]] = [
        (
            f.name,
            str(f.founder_id),
            FounderCallback(founder_id=f.founder_id),
        )
        for f in founders
    ]

    # Используем автоматическое распределение по колонкам из utils
    return await build_inline_keyboard(items, state=state)