# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/employee_kb.py
"""
Клавиатура для выбора Employee из БД.

• Загружает всех сотрудников через метод get_employees.
• Строит InlineKeyboardMarkup с callback‑схемой EMP.
• Отображает все записи (без пагинации) для отладки.
"""

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import Employee, get_employees


class EmployeeCallback(CallbackData, prefix="EMP"):
    """CallbackData для выбора сотрудника."""
    employee_id: int


async def create_employee_keyboard(session: AsyncSession, state=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех сотрудников.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    employees = await get_employees(session)  # type: List[Employee]
    items: List[tuple[str, str, EmployeeCallback]] = [
        (
            emp.name,
            str(emp.employee_id),
            EmployeeCallback(employee_id=emp.employee_id),
        )
        for emp in employees
    ]

    # Используем автоматическое распределение по колонкам из utils
    return await build_inline_keyboard(items, state=state)