# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/income/confirm_income_router.py
"""
Роутер для обработки суммы, комментария и подтверждения операции «Приход».
"""

from __future__ import annotations

from typing import Final

from aiogram import Router, Bot, F
from aiogram.filters import StateFilter, BaseFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.state import OperationState, reset_state
from src.bot.utils.legacy_messages import delete_key_messages, delete_tracked_messages, track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_wallet, create_income, get_project, get_creditor, get_founder

router: Final = Router()
log = configure_logger(prefix="CONFIRM_INCOME", color="cyan", level="INFO")


# ──────────────────────────── CallbackData ─────────────────────────
class IncomeConfirmCallback(CallbackData, prefix="confirm-income"):
    """CallbackData для кнопок подтверждения/отмены."""
    action: str  # "yes" | "no"


# ──────────────────────────── Клавиатура ───────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=IncomeConfirmCallback(action="yes").pack())
    kb.button(text="🚫 Отклонить", callback_data=IncomeConfirmCallback(action="no").pack())
    kb.adjust(2)
    return kb


# ───────────────────── Формирование сообщения ──────────────────────
async def format_operation_message(data: dict) -> str:
    wallet_id = data.get("income_wallet")
    article_id = data.get("income_article", "Не выбрано")
    amount = data.get("operation_amount", 0)
    comment = data.get("operation_comment", "—")
    op_date = data.get("operation_date", "Не выбрано")

    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id

    # Формируем строку для дополнительной информации, если она есть
    additional_info = ""
    if data.get("income_project"):
        project = await get_project(session, data["income_project"])
        additional_info = f"Проект: <b>{project.name if project else data['income_project']}</b>\n"
    elif data.get("income_creditor"):
        creditor = await get_creditor(session, data["income_creditor"])
        additional_info = f"Кредитор: <b>{creditor.name if creditor else data['income_creditor']}</b>\n"
    elif data.get("income_founder"):
        founder = await get_founder(session, data["income_founder"])
        additional_info = f"Учредитель: <b>{founder.name if founder else data['income_founder']}</b>\n"

    return (
        f"Дата: <code>{op_date}</code>\n"
        f"Тип операции: <b>Поступление</b>\n"
        f"Кошелёк: <b>{wallet_number}</b>\n"
        f"Статья: <b>{article_id}</b>\n"
        f"{additional_info if additional_info else ''}"
        f"Введённая <b>сумма</b>: <code>{amount}</code>\n"
        f"Комментарий: <i>{comment}</i>"
    )

# ─────────────────────── Custom Filter ────────────────────────────
class IncomeOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return data.get("operation_type") == "Поступление"

# ─────────────── Шаг 8: комментарий → подтверждение ────────────────
@router.message(StateFilter(OperationState.entering_operation_comment), IncomeOperationFilter())
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)

    data = await state.get_data()
    chat_id = msg.chat.id

    # Удаляем предыдущие сообщения
    await msg.delete()
    await bot.delete_message(chat_id, data.get("comment_message_id") - 1)
    await bot.delete_message(chat_id, data.get("date_message_id"))
    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    # Формируем и отправляем сообщение подтверждения
    operation_info = await format_operation_message(data)
    confirm_text = f"Подтвердите операцию:\n{operation_info}\n\nНажмите кнопку для подтверждения: ✅"
    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=confirm_text,
        reply_markup=create_confirm_keyboard().as_markup(),
        parse_mode="HTML"
    )
    await state.update_data(confirm_message_id=sent_message.message_id)
    await state.set_state(OperationState.confirming_operation)


# ─────────────────────────── YES ──────────────────────────────────
@router.callback_query(
    IncomeConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_yes(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: IncomeConfirmCallback
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info("User %s подтвердил операцию", cb.from_user.id)
    try:
        async with get_async_session() as session:
            income_data = {
                "recording_date": data.get("recording_date"),
                "operation_date": data.get("operation_date"),
                "income_wallet": data.get("income_wallet"),
                "income_article": data.get("income_article"),
                "income_project": data.get("income_project"),
                "income_creditor": data.get("income_creditor"),
                "income_founder": data.get("income_founder"),
                "operation_amount": data.get("operation_amount"),
                "operation_comment": data.get("operation_comment"),
            }
            # Удаляем пустые или None значения, чтобы избежать ошибок
            income_data = {k: v for k, v in income_data.items() if v is not None}
            income_obj = await create_income(session, income_data)

            log.info(
                f"Создан Income {income_obj.transaction_id}, Дата: {income_obj.operation_date}, "
                f"Кошелёк: {income_obj.income_wallet}, Сумма: {income_obj.operation_amount}"
            )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Поступление успешно добавлено ✅\n{info}",
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
        await reset_state(state)
    except Exception as e:
        log.error(f"Ошибка при добавлении операции: {e}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Ошибка при добавлении поступления:\n{info}\n\n{e} ❌",
            parse_mode="HTML",
        )

    await cb.answer()


# ─────────────────────────── NO ───────────────────────────────────
@router.callback_query(
    IncomeConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_no(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: IncomeConfirmCallback
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
        text=f"Добавление поступления отменено:\n{info} 🚫",
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
    await reset_state(state)
    await cb.answer()