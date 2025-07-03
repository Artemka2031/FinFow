# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/confirm_outcome_router.py
"""Подтверждение операции «Выбытие» (сумма → коэффициент → комментарий → YES/NO)."""

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
    create_outcome,
    get_async_session,
    get_wallet,
    get_creditor,
    get_project,
    get_article,
    get_contractor,
    get_material,
    get_employee,
    get_founder,
)

# ───────────────────────────── UI‑КОНСТАНТЫ ──────────────────────────────
EMO_CONFIRM  = "✅"
EMO_CANCEL   = "🚫"
EMO_REPEAT   = "🔄"
EMO_WALLET   = "🏦"
EMO_CREDITOR = "🤝"
EMO_PROJECT  = "🗂️"
EMO_GENERAL  = "📂"
EMO_ARTICLE  = "📄"
EMO_AMOUNT   = "💰"
EMO_COEFF    = "📈"

BTN_CONFIRM_TEXT: Final = f"{EMO_CONFIRM} Подтвердить"
BTN_CANCEL_TEXT:  Final = f"{EMO_CANCEL} Отклонить"

# ─────────────────────────── РОУТЕР И ЛОГГЕР ─────────────────────────────
router: Final = Router()
log = configure_logger(prefix="CONF_OUT", color="red", level="INFO")

# ─────────────────────────── CallbackData ────────────────────────────────
class OutcomeConfirmCallback(CallbackData, prefix="confirm-outcome"):
    action: str  # "yes" | "no"

# ──────────────────────────── Клавиатура ─────────────────────────────────
def create_confirm_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text=BTN_CONFIRM_TEXT, callback_data=OutcomeConfirmCallback(action="yes").pack())
    kb.button(text=BTN_CANCEL_TEXT,  callback_data=OutcomeConfirmCallback(action="no").pack())
    kb.adjust(2)
    return kb

# ─────────────────── Формирование итоговой сводки ───────────────────────
async def format_operation_message(data: dict) -> str:
    """Сводка выбытия с коэффициентом, если есть."""
    wallet_id   = data.get("outcome_wallet")
    creditor_id = data.get("outcome_creditor")
    chapter_id  = data.get("outcome_chapter")
    article_id  = data.get("outcome_article")
    saving_coeff = data.get("saving_coeff")  # NEW
    amount      = abs(data.get("operation_amount", 0))
    comment     = data.get("operation_comment", "—")
    op_date     = data.get("operation_date", "Не выбрано")

    async with get_async_session() as session:
        # источник
        if wallet_id:
            wallet = await get_wallet(session, wallet_id)
            src = f"{EMO_WALLET} Источник: <b>{wallet.wallet_number}</b>\n"
        elif creditor_id:
            cred = await get_creditor(session, creditor_id)
            src = f"{EMO_CREDITOR} Источник: <b>{cred.name}</b>\n"
        else:
            src = "Источник: <b>Не указан</b>\n"

        # раздел
        if chapter_id:
            proj = await get_project(session, chapter_id)
            chapter_line = (
                f"{EMO_PROJECT} Категория: <b>По проектам</b>\n"
                f"   {EMO_PROJECT} Проект: <b>{proj.name}</b>\n"
            )
        else:
            chapter_line = f"{EMO_GENERAL} Категория: <b>Общие</b>\n"

        # статья
        art_line = ""
        if article_id:
            art = await get_article(session, article_id)
            art_line = f"{EMO_ARTICLE} Статья: <b>{art.name if art else article_id}</b>\n"

        # уточнители
        extra = ""
        if cid := data.get("contractor_id"):
            contr = await get_contractor(session, cid)
            extra += f"👷 Подрядчик: <b>{contr.name}</b>\n"
        if mid := data.get("material_id"):
            mat = await get_material(session, mid)
            extra += f"🧱 Материал: <b>{mat.name}</b>\n"
        if eid := data.get("employee_id"):
            emp = await get_employee(session, eid)
            extra += f"👤 Сотрудник: <b>{emp.name}</b>\n"
        if art_cred := data.get("outcome_article_creditor"):
            extra += f"{EMO_CREDITOR} Кредитор (ст.29): <b>{art_cred}</b>\n"
        if fid := data.get("outcome_founder_id"):
            founder = await get_founder(session, fid)
            extra += f"🏢 Учредитель: <b>{founder.name}</b>\n"

    amount_str = f"{amount:,.2f}".replace(",", " ")  # НБ‑пробел

    coeff_line = (
        f"{EMO_COEFF} Коэффициент экономии: <b>{saving_coeff:.2f}</b>\n"
        if saving_coeff is not None else ""
    )

    return (
        f"🟥 <b>Выбытие</b> | Дата: <code>{op_date}</code>\n"
        f"{src}{chapter_line}{art_line}{extra}"
        f"{coeff_line}"
        f"{EMO_AMOUNT} Сумма: <b>{amount_str}</b> ₽\n"
        f"📝 Комментарий: <i>{comment}</i>"
    )

# ─────────────────────── Пользовательский фильтр ─────────────────────────
class OutcomeOperationFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        return (await state.get_data()).get("operation_type") == "Выбытие"

# ───────────── комментарий → подтверждение ───────────────────────────────
@router.message(StateFilter(OperationState.entering_operation_comment), OutcomeOperationFilter())
@track_messages
async def handle_comment(msg: Message, state: FSMContext, bot: Bot) -> None:
    comment = (msg.text or "").strip()
    await state.update_data(operation_comment=comment)
    log.info(f"Юзер {msg.from_user.full_name} ({msg.from_user.id}): добавил комментарий")

    data = await state.get_data()
    chat_id = msg.chat.id
    await msg.delete()

    info = await format_operation_message(data)
    sent = await bot.send_message(
        chat_id,
        f"Подтвердите операцию:\n{info}\n\nНажмите {EMO_CONFIRM} для подтверждения:",
        reply_markup=create_confirm_keyboard().as_markup(),
        parse_mode="HTML",
    )
    await state.update_data(confirm_message_id=sent.message_id)
    await state.set_state(OperationState.confirming_operation)

# ─────────────────────── ПОДТВЕРЖДЕНИЕ (YES) ────────────────────────────
@router.callback_query(
    OutcomeConfirmCallback.filter(F.action == "yes"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_yes(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: OutcomeConfirmCallback,  # noqa: ARG001
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): подтвердил выбытие")

    try:
        async with get_async_session() as session:
            outcome_data = {
                "recording_date":  data.get("recording_date"),
                "operation_date":  data.get("operation_date"),
                "outcome_wallet":  data.get("outcome_wallet"),
                "outcome_creditor": data.get("outcome_creditor"),
                "outcome_chapter": data.get("outcome_chapter"),
                "outcome_article": data.get("outcome_article"),
                "contractor_name": data.get("contractor_id"),
                "material_name":   data.get("material_id"),
                "employee_name":   data.get("employee_id"),
                "outcome_founder": data.get("outcome_founder_id"),
                "outcome_article_creditor": data.get("outcome_article_creditor"),
                "saving_coeff":    data.get("saving_coeff"),  # NEW
                "operation_amount": -abs(data.get("operation_amount", 0)),
                "operation_comment": data.get("operation_comment"),
            }
            outcome_data = {k: v for k, v in outcome_data.items() if v is not None}
            outcome_obj = await create_outcome(session, outcome_data)

            log.info(
                f"Создан Outcome {outcome_obj.transaction_id} – "
                f"Дата: {outcome_obj.operation_date}, "
                f"Источник: {outcome_obj.outcome_wallet or outcome_obj.outcome_creditor}, "
                f"Сумма: {outcome_obj.operation_amount}, "
                f"Коэфф.: {outcome_obj.saving_coeff}"
            )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Выбытие успешно добавлено {EMO_CONFIRM}\n{info}",
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, f"Выберите следующую операцию: {EMO_REPEAT}")
        await reset_state(state)
    except Exception as err:  # noqa: BLE001
        log.error(f"Ошибка при добавлении выбытия: {err}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Ошибка при добавлении выбытия:\n{info}\n\n{err} {EMO_CANCEL}",
            parse_mode="HTML",
        )

    await cb.answer()

# ───────────────────────── ОТКЛОНЕНИЕ (NO) ──────────────────────────────
@router.callback_query(
    OutcomeConfirmCallback.filter(F.action == "no"),
    OperationState.confirming_operation,
)
@track_messages
async def confirm_no(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: OutcomeConfirmCallback,  # noqa: ARG001
) -> None:
    data = await state.get_data()
    chat_id, message_id = cb.message.chat.id, cb.message.message_id
    info = await format_operation_message(data)

    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): отменил выбытие")

    await delete_tracked_messages(bot, state, chat_id)
    await delete_key_messages(bot, state, chat_id)

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"Добавление выбытия отменено:\n{info} {EMO_CANCEL}",
        parse_mode="HTML",
    )
    await bot.send_message(chat_id, f"Выберите следующую операцию: {EMO_REPEAT}")
    await reset_state(state)
    await cb.answer()
