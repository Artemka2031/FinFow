# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/income/income_router.py
"""Роутер обработки операций типа «Приход»."""

from __future__ import annotations

from typing import Final, Tuple

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.article_kb import create_article_keyboard, ArticleCallback
from src.bot.keyboards.creditor_kb import create_creditor_keyboard, CreditorCallback
from src.bot.keyboards.founder_kb import create_founder_keyboard, FounderCallback
from src.bot.keyboards.project_kb import create_project_keyboard, ProjectCallback
from src.bot.keyboards.wallet_kb import create_wallet_keyboard, WalletCallback
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import (
    get_async_session,
    get_articles,
    get_wallet,
    get_project,
    get_creditor,
    get_founder,
)

# ─────────────────────────── КОНСТАНТЫ UI ──────────────────────────────
EMOJI_INCOME:   Final = "🟢"
EMOJI_ARTICLE:  Final = "📋"
EMOJI_AMOUNT:   Final = "💰"

PROJECT_LABEL:  Final = "Название проекта"
CREDITOR_LABEL: Final = "Название кредитора"
FOUNDER_LABEL:  Final = "Название учредителя"

MSG_CHOOSE_WALLET:    Final = f"{EMOJI_INCOME} Выберите <b>кошелёк для поступления</b>:"
MSG_CHOOSE_ARTICLE:   Final = f"{EMOJI_ARTICLE} Выберите <b>статью прихода</b>:"
MSG_ENTER_AMOUNT:     Final = f"{EMOJI_AMOUNT} Введите <b>сумму</b> прихода (в рублях):"
MSG_ENTER_ADD_INFO:   Final = (
    "📝 Введите дополнительную информацию "
    f"({PROJECT_LABEL}, {CREDITOR_LABEL}, {FOUNDER_LABEL}) "
    "или «-» для пропуска:"
)

# ──────────────────────────── РОУТЕР И ЛОГГЕР ──────────────────────────
router: Final = Router()
log = configure_logger(prefix="INCOME", color="green", level="INFO")

# ──────────────────────────── HELPERS ─────────────────────────────────
async def _choose_income_wallet_msg() -> Tuple[str, InlineKeyboardMarkup]:
    """Текст и клавиатура выбора кошелька прихода."""
    async with get_async_session() as session:
        kb = await create_wallet_keyboard(session)
    return MSG_CHOOSE_WALLET, kb


async def _choose_income_article_msg(
    state: FSMContext,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Текст и клавиатура выбора статьи прихода."""
    async with get_async_session() as session:
        kb = await create_article_keyboard(session, state=state, operation_type="Поступление")

        wallet_id = (await state.get_data()).get("income_wallet")
        if wallet_id:
            wallet = await get_wallet(session, wallet_id)
            wallet_number = wallet.wallet_number if wallet else wallet_id
            text = f"Выбран кошелёк: <b>{wallet_number}</b>\n{MSG_CHOOSE_ARTICLE}"
        else:
            text = MSG_CHOOSE_ARTICLE

    return text, kb

# ─────────────────────── ВЫБОР КОШЕЛЬКА ПРИХОДА ──────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_income_wallet)
@track_messages
async def set_income_wallet(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: WalletCallback,  # noqa: ARG001
) -> None:
    wallet_id = callback_data.wallet_id
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
        wallet_number = wallet.wallet_number if wallet else wallet_id

    await state.update_data(
        income_wallet=wallet_id,
        state_history=[OperationState.choosing_income_wallet.state],
    )
    log.info(
        f"Юзер {cb.from_user.full_name}: выбран income_wallet – {wallet_id}, "
        f"кошелёк – {wallet_number}"
    )

    # Отправляем сообщение с выбором статьи
    text, kb = await _choose_income_article_msg(state)
    msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
    await state.update_data(article_message_id=msg.message_id)

    await state.set_state(OperationState.choosing_income_article)
    await cb.answer()
    await cb.message.delete()

# ─────────────────────── ВЫБОР СТАТЬИ ПРИХОДА ────────────────────────
@router.callback_query(ArticleCallback.filter(), OperationState.choosing_income_article)
@track_messages
async def set_income_article(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: ArticleCallback,  # noqa: ARG001
) -> None:
    article_id = callback_data.article_id
    await state.update_data(
        income_article=article_id,
        state_history=[OperationState.choosing_income_article.state],
    )
    log.info(f"Юзер {cb.from_user.full_name}: выбрана income_article – {article_id}")

    async with get_async_session() as session:
        # данные статьи и кошелька
        articles = await get_articles(session)
        article = next((a for a in articles if a.article_id == article_id), None)
        wallet_id = (await state.get_data()).get("income_wallet")
        wallet = await get_wallet(session, wallet_id) if wallet_id else None
        wallet_number = wallet.wallet_number if wallet else wallet_id or "Не выбрано"
        article_text = (
            f"№{article.code} {article.short_name}" if article else str(article_id)
        )

    # подтверждаем выбор
    confirm_text = (
        f"Выбран кошелёк: <b>{wallet_number}</b>\n"
        f"Выбрана статья прихода:\n✅ <b>{article_text}</b>"
    )
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    # определяем следующий шаг
    async with get_async_session() as session:
        if article and article.code in {1, 27, 28, 32}:
            if article.code == 1:
                text = f"{EMOJI_ARTICLE} Выберите <b>{PROJECT_LABEL}</b>:"
                kb = await create_project_keyboard(session, state=state)
                next_state = OperationState.choosing_income_project
            elif article.code in {27, 32}:
                text = f"{EMOJI_ARTICLE} Выберите <b>{CREDITOR_LABEL}</b>:"
                kb = await create_creditor_keyboard(session, state=state)
                next_state = OperationState.choosing_income_creditor
            else:  # article.code == 28
                text = f"{EMOJI_ARTICLE} Выберите <b>{FOUNDER_LABEL}</b>:"
                kb = await create_founder_keyboard(session, state=state)
                next_state = OperationState.choosing_income_founder
        else:
            text, kb = MSG_ENTER_AMOUNT, None
            next_state = OperationState.entering_operation_amount

    # отправляем следующий промпт
    msg = await bot.send_message(cb.message.chat.id, text, reply_markup=kb)
    await state.update_data(
        additional_info_message_id=msg.message_id if kb else None,
        amount_message_id=msg.message_id if not kb else None,
    )
    await state.set_state(next_state)
    await cb.answer()

# ──────────────────── ВЫБОР ПРОЕКТА / КРЕДИТОРА / УЧРЕДИТЕЛЯ ───────────────────
async def _handle_entity(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    entity_id: int | str,
    label: str,
    fetch_fn,
    state_key: str,
) -> None:
    async with get_async_session() as session:
        entity = await fetch_fn(session, entity_id)
        entity_name = entity.name if entity else entity_id

    await state.update_data(**{state_key: entity_id})
    log.info(f"Юзер {cb.from_user.full_name}: выбран {state_key} – {entity_id}")

    confirm_text = f"Выбран {label.lower()}:\n✅ <b>{entity_name}</b>"
    await cb.message.edit_text(confirm_text, parse_mode="HTML", reply_markup=None)

    msg = await bot.send_message(cb.message.chat.id, MSG_ENTER_AMOUNT)
    await state.update_data(amount_message_id=msg.message_id)
    await state.set_state(OperationState.entering_operation_amount)
    await cb.answer()


@router.callback_query(ProjectCallback.filter(), OperationState.choosing_income_project)
@track_messages
async def set_income_project(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: ProjectCallback,  # noqa: ARG001
) -> None:
    await _handle_entity(
        cb, state, bot, callback_data.project_id,
        PROJECT_LABEL, get_project, "income_project"
    )


@router.callback_query(CreditorCallback.filter(), OperationState.choosing_income_creditor)
@track_messages
async def set_income_creditor(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: CreditorCallback,  # noqa: ARG001
) -> None:
    await _handle_entity(
        cb, state, bot, callback_data.creditor_id,
        CREDITOR_LABEL, get_creditor, "income_creditor"
    )


@router.callback_query(FounderCallback.filter(), OperationState.choosing_income_founder)
@track_messages
async def set_income_founder(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    callback_data: FounderCallback,  # noqa: ARG001
) -> None:
    await _handle_entity(
        cb, state, bot, callback_data.founder_id,
        FOUNDER_LABEL, get_founder, "income_founder"
    )

# ─────────────────── ВВОД ДОПОЛНИТЕЛЬНОЙ ИНФО ───────────────────────────
@router.message(OperationState.choosing_income_additional_info)
@track_messages
async def set_income_additional_info(
    msg: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    info = msg.text.strip() or None
    await state.update_data(income_additional_info=info)
    log.info(f"Юзер {msg.from_user.full_name}: введена дополнительная инфо – {info}")

    await msg.delete()
    msg_amount = await bot.send_message(msg.chat.id, MSG_ENTER_AMOUNT)
    await state.update_data(amount_message_id=msg_amount.message_id)
    await state.set_state(OperationState.entering_operation_amount)
