# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/transfer/confirm_operation_router.py
"""
Роутер для обработки комментария и подтверждения/отклонения операции «Перемещение».
"""

from __future__ import annotations

from typing import Final

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter, BaseFilter
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
from src.db import get_async_session, get_wallet, create_transfer

router: Final = Router()
log = configure_logger(prefix="CONFIRM", color="green", level="INFO")


# ──────────────────────────── CallbackData ─────────────────────────
class TransferConfirmCallback(CallbackData, prefix="confirm-transfer"):
    """CallbackData для кнопок подтверждения/отмены."""
    action: str  # "yes" | "no"


# ──────────────────────────── Клавиатура ───────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Подтвердить",
        callback_data=TransferConfirmCallback(action="yes").pack(),
    )
    kb.button(
        text="🚫 Отклонить",
        callback_data=TransferConfirmCallback(action="no").pack(),
    )
    kb.adjust(2)
    return kb


# ───────────────────── Формирование сообщения ──────────────────────
async def format_operation_message(data: dict) -> str:
    from_wallet_id = data.get("from_wallet")
    to_wallet_id = data.get("to_wallet")
    amount = data.get("operation_amount", 0)
    comment = data.get("operation_comment", "—")
    op_date = data.get("operation_date", "Не выбрано")
    op_type = data.get("operation_type", "Перемещение")

    async with get_async_session() as session:
        from_num = (await get_wallet(session, from_wallet_id)).wallet_number
        to_num = (await get_wallet(session, to_wallet_id)).wallet_number

    return (
        f"Дата: <code>{op_date}</code>\n"
        f"Тип операции: <b>{op_type}</b>\n"
        f"Исходный <b>кошелёк</b>: {from_num}\n"
        f"Целевой <b>кошелёк</b>: {to_num}\n"
        f"Введённая <b>сумма</b>: <code>{amount}</code>\n"
        f"Комментарий: {comment}"
    )


# ─────────────────────── Custom Filter ────────────────────────────
class TransferOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return data.get("operation_type") == "Перемещение"

# ─────────────── Шаг 8: комментарий → подтверждение ────────────────
@router.message(StateFilter(OperationState.entering_operation_comment), TransferOperationFilter())
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)

    data = await state.get_data()
    comment_message_id = data.get("comment_message_id") - 1

    chat_id = msg.chat.id
    await msg.delete()
    await bot.delete_message(chat_id, comment_message_id)
    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    info = await format_operation_message(await state.get_data())
    confirm_text = (
        f"Подтвердите операцию:\n{info}\n\n"
        "Нажмите кнопку для выбора:"
    )

    sent = await bot.send_message(
        chat_id,
        confirm_text,
        reply_markup=create_confirm_keyboard().as_markup(),
        parse_mode="HTML",
    )
    await state.update_data(confirm_message_id=sent.message_id - 1)
    await state.set_state(OperationState.confirming_operation)


# ─────────────────────────── YES  ──────────────────────────────────
@router.callback_query(
    TransferConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_yes(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        callback_data: TransferConfirmCallback,
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info("User %s подтвердил операцию", cb.from_user.id)
    try:
        # TODO: вызов API

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
                f"Создан Transfer {transfer_obj.transaction_id}, Дата операции: {transfer_obj.operation_date},"
                f" Кошельки: {transfer_obj.from_wallet} -> {transfer_obj.to_wallet},"
                f" Сумма: {transfer_obj.operation_amount}, Комментарий: {transfer_obj.operation_comment}"
            )

        await delete_tracked_messages(bot, state, chat_id)
        await delete_key_messages(bot, state, chat_id)

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Перемещение успешно добавлено ✅\n{info}",
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
        await reset_state(state)
    except Exception as e:
        log.error(f"Ошибка при добавлении операции: {e}",)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Ошибка при добавлении перемещения:\n{info}\n\n{e} ❌",
            parse_mode="HTML",
        )

    await cb.answer()


# ─────────────────────────── NO  ───────────────────────────────────
@router.callback_query(
    TransferConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_no(
        cb: CallbackQuery,
        state: FSMContext,
        bot: Bot,
        callback_data: TransferConfirmCallback,
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info("User %s отменил операцию", cb.from_user.id)

    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"Добавление перемещения отменено:\n{info} 🚫",
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
    await reset_state(state)
    await cb.answer()
