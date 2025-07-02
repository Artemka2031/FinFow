# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/income/income_router.py
"""
Роутер для обработки операций типа «Приход».
...
"""

from __future__ import annotations

from typing import Final, Tuple

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.article_kb import create_article_keyboard, ArticleCallback
from src.bot.keyboards.creditor_kb import create_creditor_keyboard, CreditorCallback
from src.bot.keyboards.founder_kb import create_founder_keyboard, FounderCallback
from src.bot.keyboards.project_kb import create_project_keyboard, ProjectCallback
from src.bot.keyboards.wallet_kb import create_wallet_keyboard, WalletCallback
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_articles, get_wallet, get_project, get_creditor, get_founder

router: Final = Router()
log = configure_logger(prefix="INCOME", color="green", level="INFO")

# ─────────────────────────── CONSTANTS ─────────────────────────────
PROJECT_LABEL = "Название проекта"
CREDITOR_LABEL = "Название кредитора"
FOUNDER_LABEL = "Название учредителя"
ENTER_ADDITIONAL_INFO_MESSAGE = "📝 Введите дополнительную информацию ({}, {}, {}) или нажмите «-» для пропуска:".format(
    PROJECT_LABEL, CREDITOR_LABEL, FOUNDER_LABEL
)

# ──────────────────────────── HELPERS ──────────────────────────────
async def get_choose_income_wallet_message(state: FSMContext) -> Tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора кошелька прихода."""
    async with get_async_session() as session:
        kb = await create_wallet_keyboard(session)
    return "🟢 Выберите <b>кошелёк для поступления</b>:", kb


async def get_choose_income_article_message(cb: CallbackQuery, state: FSMContext) -> Tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора статьи прихода."""
    async with get_async_session() as session:
        kb = await create_article_keyboard(session, state=state, operation_type="Поступление")
    wallet_id = (await state.get_data()).get("income_wallet")
    if wallet_id:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id
        text = f"Выбран кошелёк: <b>{wallet_number}</b>\n📋 Выберите <b>статью прихода</b>:"
    else:
        text = "📋 Выберите <b>статью прихода</b>:"
    return text, kb


# ─────────────────────── CHOOSE INCOME WALLET ───────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_income_wallet)
@track_messages
async def set_income_wallet(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: WalletCallback
) -> None:
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id
    await state.update_data(income_wallet=wallet_id)
    log.info("User %s: income_wallet=%s", cb.from_user.id, wallet_id)

    # Обновляем историю состояний
    state_history = (await state.get_data()).get("state_history", [])
    await state.update_data(state_history=state_history + [OperationState.choosing_income_wallet.state])

    # Получаем данные о текущем сообщении с выбором кошелька
    wallet_data = await state.get_data()
    wallet_message_id = wallet_data.get("income_wallet_message_id", cb.message.message_id)

    # Отправляем новое сообщение с выбором статьи
    text, kb = await get_choose_income_article_message(cb, state)
    new_message = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
    await state.update_data(article_message_id=new_message.message_id)
    await state.set_state(OperationState.choosing_income_article)
    await cb.answer()
    await cb.message.delete()


# ─────────────────────── CHOOSE INCOME ARTICLE ──────────────────────
@router.callback_query(ArticleCallback.filter(), OperationState.choosing_income_article)
@track_messages
async def set_income_article(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: ArticleCallback
) -> None:
    article_id = callback_data.article_id
    await state.update_data(income_article=article_id)
    log.info("User %s: income_article=%s", cb.from_user.id, article_id)

    # Обновляем историю состояний
    state_history = (await state.get_data()).get("state_history", [])
    await state.update_data(state_history=state_history + [OperationState.choosing_income_article.state])

    # Обновляем текущее сообщение с подтверждением
    async with get_async_session() as session:
        articles = await get_articles(session)
        article = next((a for a in articles if a.article_id == article_id), None)
        wallet_id = (await state.get_data()).get("income_wallet")
        wallet = await get_wallet(session, wallet_id) if wallet_id else None
        wallet_number = wallet.wallet_number if wallet else wallet_id or "Не выбрано"
        article_text = f"№{article.code} {article.short_name}" if article else str(article_id)

    confirm_text = f"Выбран кошелёк: <b>{wallet_number}</b>\nВыбрана статья прихода:\n✅ <b>{article_text}</b>"
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    # Определяем, требуется ли дополнительная информация
    async with get_async_session() as session:
        articles = await get_articles(session)
        article = next((a for a in articles if a.article_id == article_id), None)
        if article and article.code in [1, 27, 28, 32]:  # Статьи, требующие клавиатуры
            if article.code == 1:
                text = f"📋 Выберите <b>{PROJECT_LABEL}</b>:"
                kb = await create_project_keyboard(session, state=state)
                next_state = OperationState.choosing_income_project
            elif article.code in [27, 32]:
                text = f"📋 Выберите <b>{CREDITOR_LABEL}</b>:"
                kb = await create_creditor_keyboard(session, state=state)
                next_state = OperationState.choosing_income_creditor
            elif article.code == 28:
                text = f"📋 Выберите <b>{FOUNDER_LABEL}</b>:"
                kb = await create_founder_keyboard(session, state=state)
                next_state = OperationState.choosing_income_founder
        else:  # Статьи без дополнительной информации
            text = "💰 Введите <b>сумму</b> прихода (в рублях):"
            kb = None
            next_state = OperationState.entering_operation_amount

    # Отправляем сообщение с соответствующей клавиатурой или переходим к сумме
    if kb:
        message = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
    else:
        message = await bot.send_message(cb.message.chat.id, text)
    await state.update_data(additional_info_message_id=message.message_id if kb else None, amount_message_id=message.message_id if not kb else None)
    await state.set_state(next_state)
    await cb.answer()


# ───────────────────── CHOOSE INCOME PROJECT ───────────────────────
@router.callback_query(ProjectCallback.filter(), OperationState.choosing_income_project)
@track_messages
async def set_income_project(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: ProjectCallback
) -> None:
    project_id = callback_data.project_id
    async with get_async_session() as session:
        project = await get_project(session, project_id)
        project_name = project.name if project else project_id
    await state.update_data(income_project=project_id)
    log.info("User %s: income_project=%s", cb.from_user.id, project_id)

    confirm_text = f"Выбран {PROJECT_LABEL.lower()}:\n✅ <b>{project_name}</b>"
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    # Переходим к вводу суммы
    amount_message = await bot.send_message(cb.message.chat.id, "💰 Введите <b>сумму</b> прихода (в рублях):")
    await state.update_data(amount_message_id=amount_message.message_id)
    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()


# ───────────────────── CHOOSE INCOME CREDITOR ──────────────────────
@router.callback_query(CreditorCallback.filter(), OperationState.choosing_income_creditor)
@track_messages
async def set_income_creditor(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: CreditorCallback
) -> None:
    creditor_id = callback_data.creditor_id
    async with get_async_session() as session:
        creditor = await get_creditor(session, creditor_id)
        creditor_name = creditor.name if creditor else creditor_id
    await state.update_data(income_creditor=creditor_id)
    log.info("User %s: income_creditor=%s", cb.from_user.id, creditor_id)

    confirm_text = f"Выбран {CREDITOR_LABEL.lower()}:\n✅ <b>{creditor_name}</b>"
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    # Переходим к вводу суммы
    amount_message = await bot.send_message(cb.message.chat.id, "💰 Введите <b>сумму</b> прихода (в рублях):")
    await state.update_data(amount_message_id=amount_message.message_id)
    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()


# ───────────────────── CHOOSE INCOME FOUNDER ──────────────────────
@router.callback_query(FounderCallback.filter(), OperationState.choosing_income_founder)
@track_messages
async def set_income_founder(
        cb: CallbackQuery, state: FSMContext, bot: Bot, callback_data: FounderCallback
) -> None:
    founder_id = callback_data.founder_id
    async with get_async_session() as session:
        founder = await get_founder(session, founder_id)
        founder_name = founder.name if founder else founder_id
    await state.update_data(income_founder=founder_id)
    log.info("User %s: income_founder=%s", cb.from_user.id, founder_id)

    confirm_text = f"Выбран {FOUNDER_LABEL.lower()}:\n✅ <b>{founder_name}</b>"
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    # Переходим к вводу суммы
    amount_message = await bot.send_message(cb.message.chat.id, "💰 Введите <b>сумму</b> прихода (в рублях):")
    await state.update_data(amount_message_id=amount_message.message_id)
    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()


# ───────────────────── ENTER ADDITIONAL INFO ───────────────────────
@router.message(OperationState.choosing_income_additional_info)
@track_messages
async def set_income_additional_info(msg: Message, state: FSMContext, bot: Bot) -> None:
    additional_info = msg.text.strip() or None
    await state.update_data(income_additional_info=additional_info)
    log.info("User %s: income_additional_info=%s", msg.from_user.id, additional_info)

    # Удаляем сообщение пользователя
    await msg.delete()

    # Переходим к вводу суммы
    amount_message = await bot.send_message(msg.chat.id, "💰 Введите <b>сумму</b> прихода (в рублях):")
    await state.update_data(amount_message_id=amount_message.message_id)
    await state.set_state(OperationState.entering_operation_amount)