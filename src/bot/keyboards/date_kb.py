# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/date_kb.py
from __future__ import annotations

import calendar
from datetime import datetime

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendarCallback
from aiogram_calendar.common import GenericCalendar
from aiogram_calendar.schemas import SimpleCalAct


class CustomSimpleCalendar(GenericCalendar):
    async def start_calendar(
        self,
        year: int = datetime.now().year,
        month: int = datetime.now().month
    ) -> InlineKeyboardMarkup:
        today = datetime.now()
        now_month, now_year, now_day = today.month, today.year, today.day

        def highlight_month():
            month_str = self._labels.months[month - 1]
            if now_month == month and now_year == year:
                return f"[{month_str}]"
            return month_str

        def highlight_day():
            day_string = str(day)
            if now_month == month and now_year == year and now_day == day:
                return f"[{day_string}]"
            return day_string

        # Building a calendar keyboard without year row
        kb = []

        # Month nav Buttons (without year)
        month_row = [
            InlineKeyboardButton(
                text="<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_m, year=year, month=month, day=1).pack()
            ),
            InlineKeyboardButton(
                text=highlight_month(),
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.ignore).pack()
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_m, year=year, month=month, day=1).pack()
            )
        ]
        kb.append(month_row)

        # Week Days
        week_days_labels_row = [
            InlineKeyboardButton(
                text=weekday,
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.ignore).pack()
            ) for weekday in self._labels.days_of_week
        ]
        kb.append(week_days_labels_row)

        # Calendar rows - Days of month
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            days_row = []
            for day in week:
                if day == 0:
                    days_row.append(InlineKeyboardButton(
                        text=" ",
                        callback_data=SimpleCalendarCallback(act=SimpleCalAct.ignore).pack()
                    ))
                    continue
                days_row.append(InlineKeyboardButton(
                    text=highlight_day(),
                    callback_data=SimpleCalendarCallback(act=SimpleCalAct.day, year=year, month=month, day=day).pack()
                ))
            kb.append(days_row)

        # Nav today & cancel buttons
        cancel_row = [
            InlineKeyboardButton(
                text="Отмена",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.cancel, year=year, month=month, day=day).pack()
            ),
            InlineKeyboardButton(
                text=" ",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.ignore).pack()
            ),
            InlineKeyboardButton(
                text="Сегодня",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.today, year=year, month=month, day=day).pack()
            )
        ]
        kb.append(cancel_row)

        return InlineKeyboardMarkup(row_width=7, inline_keyboard=kb)

async def create_date_kb() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора даты с кастомным календарем."""
    today = datetime.now().date()  # Текущая дата: 2025-06-30
    calendar = await CustomSimpleCalendar(locale="ru").start_calendar(
        year=today.year,
        month=today.month
    )

    # Инициализируем builder
    builder = InlineKeyboardBuilder()

    # Добавляем строки календаря
    for row in calendar.inline_keyboard:
        builder.row(*row)

    return builder.as_markup()