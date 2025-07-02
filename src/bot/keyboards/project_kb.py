# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/project_kb.py
"""
Inline‑клавиатура для выбора проекта (`Project`) из базы данных.

• Загружает все проекты через метод `get_projects`.
• Строит `InlineKeyboardMarkup` с callback‑схемой `ProjectCallback`.
• Пока без пагинации (для отладки выводит все записи в одну колонку).
"""

from typing import List

from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.bot.keyboards import NavCallback
from src.db import get_projects, Project  # предполагается, что get_projects экспортируется в src/db/__init__.py


class ProjectCallback(CallbackData, prefix="PRJ"):
    """CallbackData для выбора проекта."""
    project_id: int


async def create_project_keyboard(session: AsyncSession, state=None) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком всех проектов.

    Args:
        session: активная AsyncSession.
        state: FSMContext для добавления кнопки «Назад» (опционально).

    Returns:
        InlineKeyboardMarkup с кнопками вида [<name>].
    """
    projects = await get_projects(session)  # type: List[Project]
    items: List[tuple[str, str, ProjectCallback]] = [
        (
            proj.name,
            str(proj.project_id),
            ProjectCallback(project_id=proj.project_id),
        )
        for proj in projects
    ]

    # max_cols=1 — одна кнопка в строке, без «Назад»
    return await build_inline_keyboard(items, state=state)