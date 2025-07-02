# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/utils.py
"""
Утилиты для создания InlineKeyboardMarkup с адаптивным размещением кнопок.
"""

from typing import List, Optional, Tuple
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from src.bot.state import OperationState

async def build_inline_keyboard(
    items: List[Tuple[str, str, CallbackData]],
    state: Optional[FSMContext] = None,
    max_cols: int = 2,
    max_text_length: int = 17,
) -> InlineKeyboardMarkup:
    """
    Формирует клавиатуру, автоматически «ломая» строки:

    • Кнопка, чей текст длиннее `max_text_length`, занимает свою строку.
    • Все прочие кнопки группируются по `max_cols` в строке.
    • После длинной кнопки короткие снова группируются (буфер обнуляется).
    • Если передан `state` и текущее состояние существует, добавляется «←Назад»
      с сохранением `prev_state`.

    Args:
        items: [(text, any_id, CallbackData), …].
        state: FSMContext для сохранения prev_state и динамического добавления «Назад».
        max_cols: максимум кнопок‑столбцов для коротких текстов.
        max_text_length: длина текста, после которой кнопка считается «длинной».

    Returns:
        InlineKeyboardMarkup
    """
    rows: List[List[InlineKeyboardButton]] = []
    buffer: List[InlineKeyboardButton] = []

    for text, any_id, cb in items:
        button = InlineKeyboardButton(text=text, callback_data=cb.pack())

        # Длинная кнопка — отдельная строка
        if len(text) > max_text_length:
            if buffer:
                rows.append(buffer)
                buffer = []
            rows.append([button])
            continue

        # Короткая кнопка — кладём в буфер
        buffer.append(button)
        if len(buffer) == max_cols:
            rows.append(buffer)
            buffer = []

    # Добавляем «хвост» буфера, если остались кнопки
    if buffer:
        rows.append(buffer)

    # Добавляем кнопку «Назад», если есть состояние
    if state is not None:
        current_state = await state.get_state()  # Ожидаем корутину
        if current_state:
            await state.update_data(prev_state=current_state)
            rows.append([InlineKeyboardButton(text="← Назад", callback_data="nav:back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)