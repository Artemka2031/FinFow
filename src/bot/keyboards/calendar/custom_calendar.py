# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/calendar/custom_calendar.py
from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Tuple, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .schemas import CustomCalendarCallback, CustomCalAct, highlight
from .common import GenericCalendar

class CustomCalendar(GenericCalendar):
    def __init__(
        self,
        locale: str = "ru",
        cancel_btn: str = "Отмена",
        today_btn: str = "Сегодня",
        yesterday_btn: str = "Вчера",
        show_alerts: bool = False
    ) -> None:
        super().__init__(locale, cancel_btn, today_btn, show_alerts)
        self._labels.yesterday_caption = yesterday_btn

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
                return highlight(month_str)
            return month_str

        def highlight_day():
            day_string = str(day)
            if now_month == month and now_year == year and now_day == day:
                return highlight(day_string)
            return day_string

        builder = InlineKeyboardBuilder()

        # Строка с названием месяца и навигацией
        month_row = [
            InlineKeyboardButton(
                text="<",
                callback_data=CustomCalendarCallback(act=CustomCalAct.prev_m, year=year, month=month, day=1).pack()
            ),
            InlineKeyboardButton(
                text=highlight_month(),
                callback_data=CustomCalendarCallback(act=CustomCalAct.ignore).pack()
            ),
            InlineKeyboardButton(
                text=">",
                callback_data=CustomCalendarCallback(act=CustomCalAct.next_m, year=year, month=month, day=1).pack()
            )
        ]
        builder.row(*month_row)

        # Строка с днями недели
        week_days_row = [
            InlineKeyboardButton(
                text=weekday,
                callback_data=CustomCalendarCallback(act=CustomCalAct.ignore).pack()
            ) for weekday in self._labels.days_of_week
        ]
        builder.row(*week_days_row)

        # Строки с днями месяца
        month_cal = calendar.monthcalendar(year, month)
        for week in month_cal:
            days_row = []
            for day in week:
                if day == 0:
                    days_row.append(InlineKeyboardButton(
                        text=" ",
                        callback_data=CustomCalendarCallback(act=CustomCalAct.ignore).pack()
                    ))
                    continue
                days_row.append(InlineKeyboardButton(
                    text=highlight_day(),
                    callback_data=CustomCalendarCallback(act=CustomCalAct.day, year=year, month=month, day=day).pack()
                ))
            builder.row(*days_row)

        # Строка с кнопками "Отмена", "Вчера" и "Сегодня"
        cancel_row = [
            InlineKeyboardButton(
                text=self._labels.cancel_caption,
                callback_data=CustomCalendarCallback(act=CustomCalAct.cancel, year=year, month=month, day=day).pack()
            ),
            InlineKeyboardButton(
                text=self._labels.yesterday_caption,
                callback_data=CustomCalendarCallback(act=CustomCalAct.yesterday, year=year, month=month, day=day).pack()
            ),
            InlineKeyboardButton(
                text=self._labels.today_caption,
                callback_data=CustomCalendarCallback(act=CustomCalAct.today, year=year, month=month, day=day).pack()
            )
        ]
        builder.row(*cancel_row)

        return builder.as_markup()

    async def _update_calendar(self, query: CallbackQuery, year: int, month: int):
        new_calendar = await self.start_calendar(year, month)
        await query.message.edit_reply_markup(reply_markup=new_calendar)

    async def process_selection(self, query: CallbackQuery, data: CustomCalendarCallback) -> Tuple[bool, Optional[datetime]]:
        return_data = (False, None)

        if data.act == CustomCalAct.ignore:
            await query.answer(cache_time=60)
            return return_data

        temp_date = datetime(int(data.year), int(data.month), 1)

        # Выбор дня
        if data.act == CustomCalAct.day:
            return await self.process_day_select(data, query)

        # Навигация по месяцам
        if data.act == CustomCalAct.prev_m:
            prev_date = temp_date - timedelta(days=1)
            await self._update_calendar(query, prev_date.year, prev_date.month)
        elif data.act == CustomCalAct.next_m:
            next_date = temp_date + timedelta(days=31)
            await self._update_calendar(query, next_date.year, next_date.month)

        # Отмена
        elif data.act == CustomCalAct.cancel:
            await query.message.delete()

        return return_data