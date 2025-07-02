# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/confirm_outcome_router.py
"""
Роутер для обработки суммы, комментария и подтверждения операции «Выбытие».
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
from src.db import get_async_session, get_wallet, create_outcome, get_project, get_creditor, get_article, \
    get_contractor, get_material, get_employee, get_founder

router: Final = Router()
log = configure_logger(prefix="CONFIRM_OUTCOME", color="red", level="INFO")


# ──────────────────────────── CallbackData ─────────────────────────
class OutcomeConfirmCallback(CallbackData, prefix="confirm-outcome"):
    """CallbackData для кнопок подтверждения/отмены."""
    action: str  # "yes" | "no"


# ──────────────────────────── Клавиатура ───────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=OutcomeConfirmCallback(action="yes").pack())
    kb.button(text="🚫 Отклонить", callback_data=OutcomeConfirmCallback(action="no").pack())
    kb.adjust(2)
    return kb


# ───────────────────── Формирование сообщения ──────────────────────
async def format_operation_message(data: dict) -> str:
    outcome_wallet = data.get("outcome_wallet")
    outcome_creditor = data.get("outcome_creditor")
    outcome_chapter = data.get("outcome_chapter")
    outcome_article = data.get("outcome_article")
    amount = data.get("operation_amount", 0)
    comment = data.get("operation_comment", "—")
    op_date = data.get("operation_date", "Не выбрано")

    async with get_async_session() as session:
        if outcome_wallet:
            wallet = await get_wallet(session, outcome_wallet)
            source = f"Кошелёк: <b>{wallet.wallet_number if wallet else outcome_wallet}</b>\n"
        elif outcome_creditor:
            creditor = await get_creditor(session, outcome_creditor)
            source = f"Кредитор: <b>{creditor.name if creditor else outcome_creditor}</b>\n"
        else:
            source = "Источник: <b>Не указан</b>\n"

        # Получаем название статьи
        article_name = "Не выбрано"
        if outcome_article:
            article = await get_article(session, outcome_article)
            article_name = article.name if article else str(outcome_article)

        # Дополнительная информация
        additional_info = ""
        if outcome_chapter:
            project = await get_project(session, outcome_chapter)
            additional_info = f"Проект: <b>{project.name if project else outcome_chapter}</b>\n"
        if data.get("contractor_id"):
            contractor = await get_contractor(session, data["contractor_id"])
            additional_info += f"Подрядчик: <b>{contractor.name if contractor else data['contractor_id']}</b>\n"
        elif data.get("material_id"):
            material = await get_material(session, data["material_id"])
            additional_info += f"Материал: <b>{material.name if material else data['material_id']}</b>\n"
        elif data.get("employee_id"):
            employee = await get_employee(session, data["employee_id"])
            additional_info += f"Сотрудник: <b>{employee.name if employee else data['employee_id']}</b>\n"
        elif data.get("outcome_article_creditor"):
            additional_info += f"Кредитор (статья 29): <b>{data['outcome_article_creditor']}</b>\n"
        elif data.get("outcome_founder_id"):
            founder = await get_founder(session, data["outcome_founder_id"])
            additional_info += f"Учредитель: <b>{founder.name if founder else data['outcome_founder_id']}</b>\n"

    return (
        f"Дата: <code>{op_date}</code>\n"
        f"Тип операции: <b>Выбытие</b>\n"
        f"{source}"
        f"Раздел: <b>{'По проектам' if outcome_chapter else 'Общие' if not outcome_chapter else 'Не указан'}</b>\n"
        f"Статья: <b>{article_name}</b>\n"
        f"{additional_info if additional_info else ''}"
        f"Введённая <b>сумма</b>: <code>{amount}</code>\n"
        f"Комментарий: <i>{comment}</i>"
    )


# ─────────────────────── Custom Filter ────────────────────────────
class OutcomeOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return data.get("operation_type") == "Выбытие"


# ─────────────── Шаг 8: комментарий → подтверждение ────────────────
@router.message(StateFilter(OperationState.entering_operation_comment), OutcomeOperationFilter())
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)

    data = await state.get_data()
    chat_id = msg.chat.id

    # Удаляем предыдущие сообщения
    await msg.delete()
    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id, exclude_message_ids=[
        data.get("summary_message_id"),
        data.get("amount_message_id"),
    ])

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
    OutcomeConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_yes(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: OutcomeConfirmCallback
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info("User %s подтвердил операцию", cb.from_user.id)
    try:
        async with get_async_session() as session:
            outcome_data = {
                "recording_date": data.get("recording_date"),
                "operation_date": data.get("operation_date"),
                "outcome_wallet": data.get("outcome_wallet"),
                "outcome_creditor": data.get("outcome_creditor"),
                "outcome_chapter": data.get("outcome_chapter"),
                "outcome_article": data.get("outcome_article"),
                "contractor_name": data.get("contractor_id"),
                "material_name": data.get("material_id"),
                "employee_name": data.get("employee_id"),
                "outcome_founder": data.get("outcome_founder_id"),
                "outcome_article_creditor": data.get("outcome_article_creditor"),
                "operation_amount": -abs(data.get("operation_amount", 0)),  # Гарантируем отрицательное значение
                "operation_comment": data.get("operation_comment"),
            }
            # Удаляем пустые или None значения
            outcome_data = {k: v for k, v in outcome_data.items() if v is not None}
            outcome_obj = await create_outcome(session, outcome_data)

            log.info(
                f"Создан Outcome {outcome_obj.transaction_id}, Дата: {outcome_obj.operation_date}, "
                f"Источник: {outcome_obj.outcome_wallet or outcome_obj.outcome_creditor}, Сумма: {outcome_obj.operation_amount}"
            )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Выбытие успешно добавлено ✅\n{info}",
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
        await reset_state(state)
    except Exception as e:
        log.error(f"Ошибка при добавлении операции: {e}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Ошибка при добавлении выбытия:\n{info}\n\n{e} ❌",
            parse_mode="HTML",
        )

    await cb.answer()


# ─────────────────────────── NO ───────────────────────────────────
@router.callback_query(
    OutcomeConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation
)
@track_messages
async def confirm_no(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: OutcomeConfirmCallback
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
        text=f"Добавление выбытия отменено:\n{info} 🚫",
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, "Выберите следующую операцию: 🔄")
    await reset_state(state)
    await cb.answer()
