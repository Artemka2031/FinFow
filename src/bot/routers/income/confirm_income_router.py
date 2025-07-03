# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/income/confirm_income_router.py
"""Роутер подтверждения операции «Приход» (сумма, комментарий, YES/NO)."""

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
from src.db import (
    create_income,
    get_async_session,
    get_wallet,
    get_project,
    get_creditor,
    get_founder, get_article,
)

# ─────────────────────────────── UI‑КОНСТАНТЫ ──────────────────────────────
EMOJI_CONFIRM: Final = "✅"
EMOJI_CANCEL:  Final = "🚫"
EMOJI_ERROR:   Final = "❌"
EMOJI_REPEAT:  Final = "🔄"

BTN_CONFIRM_TEXT: Final = f"{EMOJI_CONFIRM} Подтвердить"
BTN_CANCEL_TEXT:  Final = f"{EMOJI_CANCEL} Отклонить"

MSG_OPERATION_PROMPT: Final = (
    "Подтвердите операцию:\n{info}\n\n"
    f"Нажмите кнопку: {EMOJI_CONFIRM}"
)
MSG_INCOME_SUCCESS: Final = (
    f"Поступление успешно добавлено {EMOJI_CONFIRM}\n{{info}}"
)
MSG_INCOME_ERROR: Final = (
    "Ошибка при добавлении поступления:\n{info}\n\n{error} " + EMOJI_ERROR
)
MSG_INCOME_CANCEL: Final = (
    f"Добавление поступления отменено:\n{{info}} {EMOJI_CANCEL}"
)
MSG_NEXT_STEP: Final = f"Выберите следующую операцию: {EMOJI_REPEAT}"

# ─────────────────────────── РОУТЕР И ЛОГГЕР ─────────────────────────────
router: Final = Router()
log = configure_logger(prefix="CONFIRM_INC", color="cyan", level="INFO")

# ─────────────────────────── CallbackData ────────────────────────────────
class IncomeConfirmCallback(CallbackData, prefix="confirm-income"):
    """CallbackData для YES/NO кнопок."""
    action: str  # "yes" | "no"

# ──────────────────────────── Клавиатура ─────────────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=BTN_CONFIRM_TEXT, callback_data=IncomeConfirmCallback(action="yes").pack())
    kb.button(text=BTN_CANCEL_TEXT,  callback_data=IncomeConfirmCallback(action="no").pack())
    kb.adjust(2)
    return kb.as_markup()

# ───────────────────── Формирование сводки ──────────────────────────────
async def format_operation_message(data: dict) -> str:
    """Стильная сводка операции для подтверждения."""
    wallet_id   = data.get("income_wallet")
    article_id  = data.get("income_article", "—")
    amount      = data.get("operation_amount", 0)
    comment     = data.get("operation_comment", "—")
    op_date     = data.get("operation_date", "Не выбрано")

    async with get_async_session() as session:
        wallet   = await get_wallet(session, wallet_id)
        w_num    = wallet.wallet_number if wallet else wallet_id

        artical_name = (await get_article(session, article_id)).name

        # доп‑инфо (проект / кредитор / учредитель)
        extra = ""
        if data.get("income_project"):
            project = await get_project(session, data["income_project"])
            extra   = f"🏗️ Проект: <b>{project.name if project else data['income_project']}</b>\n"
        elif data.get("income_creditor"):
            cred    = await get_creditor(session, data["income_creditor"])
            extra   = f"🤝 Кредитор: <b>{cred.name if cred else data['income_creditor']}</b>\n"
        elif data.get("income_founder"):
            founder = await get_founder(session, data["income_founder"])
            extra   = f"🏢 Учредитель: <b>{founder.name if founder else data['income_founder']}</b>\n"

    # Красивое форматирование суммы (2 знака, пробел‑разделитель тысяч)
    amount_str = f"{amount:,.2f}".replace(',', ' ')  # не‑breakable space

    return (
        f"🟩 <b>Поступление</b> | Дата: <code>{op_date}</code>\n"
        f"📥 Кошелёк: <b>{w_num}</b>\n"
        f"📄 Статья: <b>{artical_name}</b>\n"
        f"{extra}"
        f"💰 Сумма: <b>{amount_str}</b> ₽\n"
        f"📝 Комментарий: <i>{comment}</i>"
    )


# ─────────────────────── Пользовательский фильтр ─────────────────────────
class IncomeOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:  # noqa: D401
        data = await state.get_data()
        return data.get("operation_type") == "Поступление"

# ────────────── Шаг: комментарий → подтверждение ─────────────────────────
@router.message(
    StateFilter(OperationState.entering_operation_comment),
    IncomeOperationFilter(),
)
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    """Принимаем комментарий, показываем сводку с кнопками YES/NO."""
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)
    log.info(f"Юзер {msg.from_user.full_name}: введён комментарий")

    data = await state.get_data()
    chat_id = msg.chat.id

    # чистим предыдущие сообщения
    await msg.delete()
    await bot.delete_message(chat_id, data.get("comment_message_id") - 1)
    await bot.delete_message(chat_id, data.get("date_message_id"))
    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    # отправляем подтверждение
    info = await format_operation_message(data)
    msg = str(MSG_OPERATION_PROMPT.format(info=info))
    sent = await bot.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=create_confirm_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(confirm_message_id=sent.message_id)
    await state.set_state(OperationState.confirming_operation)

# ─────────────────────── ПОДТВЕРЖДЕНИЕ (YES) ────────────────────────────
@router.callback_query(
    IncomeConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_yes(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: IncomeConfirmCallback,  # noqa: ARG001
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name}: подтвердил приход")

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
            income_data = {k: v for k, v in income_data.items() if v is not None}
            income_obj = await create_income(session, income_data)

            log.info(
                f"Создан Income {income_obj.transaction_id} – "
                f"Дата: {income_obj.operation_date}, "
                f"Кошелёк: {income_obj.income_wallet}, "
                f"Сумма: {income_obj.operation_amount}"
            )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MSG_INCOME_SUCCESS.format(info=info),
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, MSG_NEXT_STEP)
        await reset_state(state)
    except Exception as err:  # noqa: BLE001
        log.error(f"Ошибка при добавлении поступления: {err}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=MSG_INCOME_ERROR.format(info=info, error=err),
            parse_mode="HTML",
        )

    await cb.answer()

# ───────────────────────── ОТКЛОНЕНИЕ (NO) ──────────────────────────────
@router.callback_query(
    IncomeConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_no(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: IncomeConfirmCallback,  # noqa: ARG001
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name}: отменил приход")

    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=MSG_INCOME_CANCEL.format(info=info),
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, MSG_NEXT_STEP)
    await reset_state(state)
    await cb.answer()
