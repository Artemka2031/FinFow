# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/amount_comment_router.py
"""
Шаг 7  – ввод суммы
"""

from __future__ import annotations

import re
from typing import Final

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.methods import EditMessageText
from aiogram.types import Message

from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger

router: Final = Router()
log = configure_logger(prefix="AMT/CMNT", color="yellow", level="INFO")


# ──────────────────────────── Шаг 7: сумма ──────────────────────────────
@router.message(OperationState.entering_operation_amount)
@track_messages
async def handle_amount(msg: Message, state: FSMContext, bot: Bot) -> None:
    """
    Принимаем произвольный ввод: «10 000,50», «10000.5», «10 000» и т.п.
    Переходим к комментарию.
    """
    raw = msg.text or ""
    # оставляем цифры, «.» и «,»
    cleaned = re.sub(r"[^\d.,\-]", "", raw).replace(",", ".")
    # убираем лишние точки (10.000.50  →  10000.50)
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = parts[0] + "." + "".join(parts[1:])
    try:
        amount = float(cleaned)
    except ValueError:
        await msg.answer(
            "✖️ Неверный формат.\n"
            "Пример: <code>1234.56</code> или <code>1 234,56</code>"
        )
        return

    await state.update_data(operation_amount=amount)
    log.info(f"User {msg.from_user.id}: amount={amount}")

    # Получаем message_id запроса суммы и сводки из состояния
    data = await state.get_data()
    amount_message_id = data.get("amount_message_id")
    summary_message_id = data.get("summary_message_id")

    if amount_message_id:
        # Обновляем сообщение с запросом суммы
        confirm_text = f"💲 Введённая <b>сумма</b>: {amount}"
        try:
            await bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=amount_message_id,
                text=confirm_text,
                parse_mode="HTML"
            )
        except Exception as e:
            log.error(f"Ошибка при редактировании сообщения {amount_message_id}: {e}")
            await msg.answer(confirm_text, parse_mode="HTML")

    # Удаляем исходное сообщение с вводом
    await msg.delete()

    # Переходим к вводу комментария
    comment_message = await bot.send_message(
        chat_id=msg.chat.id,
        text="Добавьте комментарий к операции (или «-» для пустого)."
    )
    await state.update_data(comment_message_id=comment_message.message_id)
    await state.set_state(OperationState.entering_operation_comment)