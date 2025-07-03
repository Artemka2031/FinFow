# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/creditor_kb.py
"""
Клавиатура для выбора Creditor из БД.

• Загружает всех кредиторов через метод get_creditors.
• Строит InlineKeyboardMarkup с callback‑схемой CRD.
• Отображает все записи для отладки (без пагинации).
• Исключает текущего кредитора (outcome_creditor) при наличии в состоянии.
"""

from typing import List, Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import Creditor, get_creditors


class CreditorCallback(CallbackData, prefix="CRD"):
    """CallbackData для выбора кредитора."""
    creditor_id: int


async def create_creditor_keyboard(session: AsyncSession, state: Optional[FSMContext] = None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех кредиторов, исключая текущего кредитора из состояния.

    Args:
        session: активная AsyncSession.
        state: FSMContext для получения outcome_creditor и добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    creditors = await get_creditors(session)  # type: List[Creditor]
    exclude_creditor_id = None

    # Получаем outcome_creditor из состояния, если оно доступно
    if state:
        data = await state.get_data()
        exclude_creditor_id = data.get("outcome_creditor")

    items: List[tuple[str, str, CreditorCallback]] = [
        (
            cr.name,
            str(cr.creditor_id),
            CreditorCallback(creditor_id=cr.creditor_id),
        )
        for cr in creditors
        if cr.creditor_id != exclude_creditor_id
    ]

    # Автоматически формируем оптимальный layout: много колонок, если имена короткие
    return await build_inline_keyboard(items, state=state)