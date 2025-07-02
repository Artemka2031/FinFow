# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/calendar/__init__.py
from aiogram.types import InlineKeyboardMarkup

from .custom_calendar import CustomCalendar

async def create_date_kb() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора даты с кастомным календарем."""
    calendar = CustomCalendar(locale="ru")
    return await calendar.start_calendar()