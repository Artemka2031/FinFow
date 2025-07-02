# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/article_kb.py
"""
Клавиатура для выбора Article из БД.

• Загружает статьи через метод get_articles.
• Фильтрует статьи по типу операции или данным из state/config.
• В текст кнопки вписывает код и короткое имя в формате "№<code> <short_name>".
• Подбирает оптимальное число колонок автоматически.
"""

from typing import List, Optional

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.utils import build_inline_keyboard
from src.db import get_articles, Article
from src.core.config import get_settings

class ArticleCallback(CallbackData, prefix="ART"):
    """CallbackData для выбора статьи."""
    article_id: int


async def create_article_keyboard(
    session: AsyncSession,
    state: FSMContext = None,
    operation_type: Optional[str] = None,
    custom_article_codes: Optional[List[int]] = None
) -> InlineKeyboardMarkup:
    """
    Собирает InlineKeyboardMarkup со списком отфильтрованных статей.

    Args:
        session: активная AsyncSession.
        state: FSMContext для получения данных состояния (опционально).
        operation_type: Тип операции (Поступление, Перемещение, Выбытие) для фильтрации статей.
        custom_article_codes: Список кастомных номеров статей для экстренного случая.

    Returns:
        InlineKeyboardMarkup с кнопками вида ["№<code> <short_name>"].
    """
    settings = get_settings()
    articles = await get_articles(session)  # type: List[Article]

    # Определяем разрешенные коды статей на основе state или operation_type
    allowed_codes = set()
    if state:
        data = await state.get_data()

        project = data.get("outcome_chapter")
        finance = data.get("outcome_general_type") == "finance"
        payroll = data.get("outcome_general_type") == "payroll"

        if project:
            allowed_codes = set(settings.project_outcome_article_codes)  # 3-10
        elif finance:
            allowed_codes = set(settings.financial_outcome_article_codes)  # 11-20
        elif payroll:
            allowed_codes = set(settings.operational_outcome_article_codes)  # 21-30

    # Если задан custom_article_codes, используем его в приоритете
    if custom_article_codes is not None:
        allowed_codes = set(custom_article_codes)

    elif operation_type:
        if operation_type == "Поступление":
            allowed_codes = set(settings.income_article_codes)

    items = [
        (
            f"№{a.code} {a.short_name}",
            str(a.article_id),
            ArticleCallback(article_id=a.article_id),
        )
        for a in articles
        if a.code in allowed_codes
    ]

    return await build_inline_keyboard(items, state=state)