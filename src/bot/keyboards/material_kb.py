# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/material_kb.py
"""
Клавиатура для выбора Material из БД.

• Загружает все материалы через get_materials().
• Строит InlineKeyboardMarkup с callback‑схемой MAT.
"""

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import get_materials, Material


class MaterialCallback(CallbackData, prefix="MAT"):
    """CallbackData для выбора материала."""
    material_id: int


async def create_material_keyboard(session: AsyncSession, state=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех материалов.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    materials = await get_materials(session)  # type: List[Material]
    items = [
        (
            m.name,
            str(m.material_id),
            MaterialCallback(material_id=m.material_id)
        )
        for m in materials
    ]
    # Одна кнопка в строке
    return await build_inline_keyboard(items, state=state)