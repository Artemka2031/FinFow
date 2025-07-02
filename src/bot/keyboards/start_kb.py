# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/start_kb.py
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def create_start_kb() -> InlineKeyboardMarkup:
    """Создает клавиатуру для начального экрана с основными действиями."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Добавить расход 💸", callback_data="add_expense"),
        InlineKeyboardButton(text="Добавить доход 💰", callback_data="add_income"),
    )
    builder.add(
        InlineKeyboardButton(text="Удалить операцию ❌", callback_data="delete_operation"),
        InlineKeyboardButton(text="Начать работу с ИИ 🤖", callback_data="start_ai"),
    )
    builder.adjust(2)
    return builder.as_markup()