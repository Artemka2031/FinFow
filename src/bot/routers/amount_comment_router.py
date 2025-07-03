# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/amount_comment_router.py
"""Шаг 7 мастера — ввод суммы, при необходимости коэффициента, затем комментарий."""

from __future__ import annotations

import re
from typing import Final

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger

# ──────────────────────────── КОНСТАНТЫ UI ───────────────────────────────
EMO_AMOUNT:   Final = "💲"
EMO_ERROR:    Final = "✖️"
EMO_COEFF:    Final = "📈"

MSG_INVALID_AMOUNT: Final = (
    f"{EMO_ERROR} Неверный формат суммы.\n"
    "Пример: <code>1234.56</code> или <code>1 234,56</code>"
)
MSG_CONFIRM_AMOUNT: Final = f"{EMO_AMOUNT} Введённая <b>сумма</b>: {{amount}}"
MSG_ENTER_COEFF:    Final = f"{EMO_COEFF} Введите <b>коэффициент экономии</b> (0–1):"
MSG_INVALID_COEFF:  Final = f"{EMO_ERROR} Коэффициент должен быть числом от 0 до 1."
MSG_CONFIRM_COEFF:  Final = f"{EMO_COEFF} Коэффициент экономии: {{coeff}}"
MSG_ENTER_COMMENT:  Final = "Добавьте комментарий к операции (или «-» для пустого)."

# ──────────────────────────── РОУТЕР И ЛОГГЕР ────────────────────────────
router: Final = Router()
log = configure_logger(prefix="AMT/CMNT", color="yellow", level="INFO")

# ───────────────────────── ШАГ 7: СУММА ──────────────────────────────────
@router.message(OperationState.entering_operation_amount)
@track_messages
async def handle_amount(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Парсим сумму, подтверждаем, решаем — спрашивать ли коэффициент."""
    raw = msg.text or ""
    cleaned = re.sub(r"[^\d.,\\-]", "", raw).replace(",", ".")
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = parts[0] + "." + "".join(parts[1:])

    try:
        amount = float(cleaned)
    except ValueError:
        await msg.answer(MSG_INVALID_AMOUNT)
        return

    await state.update_data(operation_amount=amount)
    log.info(f"Юзер {msg.from_user.full_name}: введена сумма – {amount}")

    data = await state.get_data()
    amount_prompt_id = data.get("amount_message_id") - 1
    await state.update_data(amount_message_id=amount_prompt_id)

    # подтверждение в оригинальном сообщении
    if amount_prompt_id:
        confirm_text = MSG_CONFIRM_AMOUNT.format(amount=amount)
        try:
            await bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=amount_prompt_id,
                text=confirm_text,
                parse_mode="HTML",
            )
        except Exception as err:  # noqa: BLE001
            log.error(f"Ошибка при редактировании сообщения {amount_prompt_id}: {err}")
            await msg.answer(confirm_text, parse_mode="HTML")

    await msg.delete()

    # нужно ли спрашивать saving_coeff?
    op_type = data.get("operation_type")
    has_creditor = bool(data.get("outcome_creditor"))
    if op_type == "Выбытие" and has_creditor:
        coeff_msg = await bot.send_message(msg.chat.id, MSG_ENTER_COEFF)
        await state.update_data(coeff_message_id=coeff_msg.message_id)
        await state.set_state(OperationState.entering_saving_coeff)
    else:
        # сразу к комментарию
        comment_msg = await bot.send_message(msg.chat.id, MSG_ENTER_COMMENT)
        await state.update_data(comment_message_id=comment_msg.message_id)
        await state.set_state(OperationState.entering_operation_comment)

# ──────────────── ШАГ 9 (если нужен): КОЭФФИЦИЕНТ ────────────────────────
@router.message(OperationState.entering_saving_coeff)
@track_messages
async def handle_saving_coeff(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Парсим коэффициент (0–1), подтверждаем, переходим к комментарию."""
    raw = (msg.text or "").replace(",", ".").strip()
    try:
        coeff = float(raw)
        if not (0 <= coeff <= 1):
            raise ValueError
    except ValueError:
        await msg.answer(MSG_INVALID_COEFF)
        return

    await state.update_data(saving_coeff=coeff)
    log.info(f"Юзер {msg.from_user.full_name}: коэффициент экономии – {coeff}")

    # подтверждаем
    data = await state.get_data()
    coeff_prompt_id = data.get("coeff_message_id", msg.message_id - 1)
    if coeff_prompt_id:
        try:
            await bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=coeff_prompt_id,
                text=MSG_CONFIRM_COEFF.format(coeff=coeff),
                parse_mode="HTML",
            )
        except Exception as err:  # noqa: BLE001
            log.error(f"Ошибка при редактировании сообщения {coeff_prompt_id}: {err}")
            await msg.answer(MSG_CONFIRM_COEFF.format(coeff=coeff), parse_mode="HTML")

    await msg.delete()

    # переходим к комментарию
    comment_msg = await bot.send_message(msg.chat.id, MSG_ENTER_COMMENT)
    await state.update_data(comment_message_id=comment_msg.message_id)
    await state.set_state(OperationState.entering_operation_comment)
