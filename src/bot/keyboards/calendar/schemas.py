# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/calendar/schemas.py
from typing import Optional
from enum import Enum

from pydantic import BaseModel, conlist, Field
from aiogram.filters.callback_data import CallbackData

class CustomCalAct(str, Enum):
    """Перечисление действий для кастомного календаря."""
    ignore = 'IGNORE'
    prev_m = 'PREV-MONTH'
    next_m = 'NEXT-MONTH'
    cancel = 'CANCEL'
    today = 'TODAY'
    yesterday = 'YESTERDAY'  # Добавлено действие для вчера
    day = 'DAY'

class CalendarCallback(CallbackData, prefix="calendar"):
    """Базовый класс для callback-данных календаря."""
    act: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None

class CustomCalendarCallback(CalendarCallback, prefix="custom_calendar"):
    """Класс callback-данных для кастомного календаря."""
    act: CustomCalAct

class CalendarLabels(BaseModel):
    """Схема для меток календаря, поддерживающая разные языки."""
    days_of_week: conlist(str, max_length=7, min_length=7) = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months: conlist(str, max_length=12, min_length=12) = [
        "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
    ]
    cancel_caption: str = Field(default="Отмена", description="Надпись для кнопки Отмена")
    today_caption: str = Field(default="Сегодня", description="Надпись для кнопки Сегодня")
    yesterday_caption: str = Field(default="Вчера", description="Надпись для кнопки Вчера")  # Добавлено поле

HIGHLIGHT_FORMAT = "[{}]"

def highlight(text):
    """Выделяет текст квадратными скобками."""
    return HIGHLIGHT_FORMAT.format(text)

def superscript(text):
    """Преобразует текст в верхний индекс."""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-=()"
    super_s = "ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾQᴿˢᵀᵁⱽᵂˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖ۹ʳˢᵗᵘᵛʷˣʸᶻ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾"
    output = ''
    for i in text:
        output += (super_s[normal.index(i)] if i in normal else i)
    return output

def subscript(text):
    """Преобразует текст в нижний индекс."""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-=()"
    sub_s = "ₐ₈CDₑբGₕᵢⱼₖₗₘₙₒₚQᵣₛₜᵤᵥwₓᵧZₐ♭꜀ᑯₑբ₉ₕᵢⱼₖₗₘₙₒₚ૧ᵣₛₜᵤᵥwₓᵧ₂₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"
    output = ''
    for i in text:
        output += (sub_s[normal.index(i)] if i in normal else i)
    return output