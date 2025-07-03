# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/transfer/confirm_operation_router.py
"""Роутер подтверждения операции «Перемещение».

Сценарий:
    1. Юзер вводит комментарий к операции.
    2. Бот формирует сводку и запрашивает подтверждение/отклонение.
    3. Юзер подтверждает  → запись в БД, сообщение об успехе.
       Юзер отклоняет     → операция отменена.
"""

from __future__ import annotations

from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.state import OperationState, reset_state
from src.bot.utils.legacy_messages import (
    delete_key_messages,
    delete_tracked_messages,
    track_messages,
)
from src.core.logger import configure_logger
from src.db import create_transfer, get_async_session, get_wallet

# ─────────────────────────────── UI‑ТЕКСТЫ ────────────────────────────────
EMOJI_CONFIRM:  Final = "✅"
EMOJI_CANCEL:   Final = "🚫"
EMOJI_ERROR:    Final = "❌"
EMOJI_REPEAT:   Final = "🔄"

BTN_CONFIRM_TEXT: Final = f"{EMOJI_CONFIRM} Подтвердить"
BTN_CANCEL_TEXT:  Final = f"{EMOJI_CANCEL} Отклонить"

MSG_OPERATION_REQUEST: Final = (
    "Подтвердите операцию:\n{info}\n\n"
    "Нажмите кнопку для выбора:"
)
MSG_TRANSFER_SUCCESS: Final = (
    f"Перемещение успешно добавлено {EMOJI_CONFIRM}\n{{info}}"
)
MSG_TRANSFER_ERROR: Final = (
    "Ошибка при добавлении перемещения:\n{info}\n\n{{error}} {EMOJI_ERROR}"
)
MSG_TRANSFER_CANCEL: Final = (
    f"Добавление перемещения отменено:\n{{info}} {EMOJI_CANCEL}"
)
MSG_NEXT_OPERATION: Final = f"Выберите следующую операцию: {EMOJI_REPEAT}"

# ─────────────────────────── РОУТЕР И ЛОГГЕР ─────────────────────────────
router: Final = Router()
log = configure_logger(prefix="CONFIRM", color="green", level="INFO")

# ─────────────────────────── CallbackData ────────────────────────────────
class TransferConfirmCallback(CallbackData, prefix="confirm-transfer"):
    """CallbackData для кнопок подтверждения/отмены."""

    action: str  # "yes" | "no"

# ──────────────────────────── Клавиатура ─────────────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура подтверждения/отмены операции."""
    kb = InlineKeyboardBuilder()
    kb.button(
        text=BTN_CONFIRM_TEXT,
        callback_data=TransferConfirmCallback(action="yes").pack(),
    )
    kb.button(
        text=BTN_CANCEL_TEXT,
        callback_data=TransferConfirmCallback(action="no").pack(),
    )
    kb.adjust(2)
    return kb

# ─────────────────────── Формирование сводки ─────────────────────────────
async def format_operation_message(data: dict) -> str:
    """Делает «живую» сводку операции «Перемещение» для подтверждения."""

    from_wallet_id = data.get("from_wallet")
    to_wallet_id   = data.get("to_wallet")
    amount         = data.get("operation_amount", 0)
    comment        = data.get("operation_comment", "—")
    op_date        = data.get("operation_date", "Не выбрано")

    async with get_async_session() as session:
        from_num = (await get_wallet(session, from_wallet_id)).wallet_number
        to_num   = (await get_wallet(session, to_wallet_id)).wallet_number

    # красивый вывод суммы «1 234,56»
    amount_str = f"{amount:,.2f}".replace(",", " ")    # узкий неразрывный пробел

    return (
        f"🔄 <b>Перемещение</b> | Дата: <code>{op_date}</code>\n"
        f"👛 Откуда: <b>{from_num}</b>\n"
        f"📥 Куда:   <b>{to_num}</b>\n"
        f"💰 Сумма:  <b>{amount_str}</b> ₽\n"
        f"📝 Комментарий: <i>{comment}</i>"
    )


# ─────────────────────── Пользовательский фильтр ─────────────────────────
class TransferOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:  # noqa: D401
        """Пропускает сообщения, только если тип операции — «Перемещение»."""
        data = await state.get_data()
        return data.get("operation_type") == "Перемещение"

# ────────────── Шаг 8: комментарий → подтверждение ───────────────────────
@router.message(
    StateFilter(OperationState.entering_operation_comment),
    TransferOperationFilter(),
)
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает комментарий и запрашивает подтверждение операции."""
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)
    log.info(f"Юзер {msg.from_user.full_name}: введён комментарий к операции - {comment}")

    data = await state.get_data()
    prompt_id = data.get("comment_message_id") - 1  # id сообщения‑промпта

    chat_id = msg.chat.id

    info = await format_operation_message(await state.get_data())
    confirm_text = MSG_OPERATION_REQUEST.format(info=info)

    sent = await bot.send_message(
        chat_id,
        confirm_text,
        reply_markup=create_confirm_keyboard().as_markup(),
        parse_mode="HTML",
    )

    await msg.delete()
    await bot.delete_message(chat_id, prompt_id)

    log.warning(f" State data {await state.get_data()}")

    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    await state.update_data(confirm_message_id=sent.message_id - 1)
    await state.set_state(OperationState.confirming_operation)

# ──────────────────────── ПОДТВЕРЖДЕНИЕ (YES) ────────────────────────────
@router.callback_query(
    TransferConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_yes(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: TransferConfirmCallback,  # noqa: ARG001
) -> None:
    """Юзер подтвердил операцию."""
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name}: подтвердил операцию")

    try:
        async with get_async_session() as session:
            transfer_data = {
                "recording_date": data.get("recording_date"),
                "operation_date": data.get("operation_date"),
                "to_wallet": data.get("to_wallet"),
                "from_wallet": data.get("from_wallet"),
                "operation_amount": data.get("operation_amount"),
                "operation_comment": data.get("operation_comment"),
            }
            transfer_obj = await create_transfer(session, transfer_data)

            log.info(
                f"Создан Transfer {transfer_obj.transaction_id} – "
                f"Дата: {transfer_obj.operation_date}, "
                f"Кошельки: {transfer_obj.from_wallet} → {transfer_obj.to_wallet}, "
                f"Сумма: {transfer_obj.operation_amount}, "
                f"Комментарий: {transfer_obj.operation_comment}"
            )

        log.warning(f" State data {await state.get_data()}")

        await delete_tracked_messages(bot, state, chat_id)
        await delete_key_messages(bot, state, chat_id)

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MSG_TRANSFER_SUCCESS.format(info=info),
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, MSG_NEXT_OPERATION)
        await reset_state(state)
    except Exception as error:  # noqa: BLE001
        log.error(f"Ошибка при добавлении операции: {error}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MSG_TRANSFER_ERROR.format(info=info, error=error),
            parse_mode="HTML",
        )

    await cb.answer()

# ──────────────────────── ОТКЛОНЕНИЕ (NO) ────────────────────────────────
@router.callback_query(
    TransferConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_no(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: TransferConfirmCallback,  # noqa: ARG001
) -> None:
    """Юзер отклонил операцию."""
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name}: отменил операцию")

    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=MSG_TRANSFER_CANCEL.format(info=info),
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, MSG_NEXT_OPERATION)
    await reset_state(state)
    await cb.answer()

# ──────────────────────────────────────────────────────────────────────────
