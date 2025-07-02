# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/outcome_router.py
"""
Роутер для обработки операций выбытия.
"""

from __future__ import annotations

from typing import Final, Callable

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.article_kb import create_article_keyboard
from src.bot.keyboards.creditor_kb import CreditorCallback, create_creditor_keyboard
from src.bot.keyboards.project_kb import create_project_keyboard
from src.bot.keyboards.wallet_kb import WalletCallback, create_wallet_keyboard
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_wallet, get_creditor, get_project

router: Final = Router()
log = configure_logger(prefix="OUTCOME", color="red", level="INFO")

# ─────────────────────────── CONSTANTS ─────────────────────────────
GENERAL_LABEL = "🌐 Общие"
PROJECT_LABEL = "📋 По проектам"

FINANCE_LABEL = "💰 Фин. операции и инвестиции"
PAYROLL_LABEL = "👥 ФОТ и другое"

BACK_LABEL = "⬅️ Назад"

# ──────────────────────────── HELPERS ──────────────────────────────
MSG_INDICATE_OUTCOME_SOURCE = "Укажите источник выбытия:"
MSG_CHOOSE_OUTCOME_CHAPTER = "📑 Выберите категорию выбытия:"
MSG_CHOOSE_OUTCOME_PROJECT = f"Выберите <b>Проект</b>:"
MSG_CHOOSE_OUTCOME_GENERAL_TYPE = "Выберите тип общих операций:"
MSG_CHOOSE_OUTCOME_ARTICLE = "📋 Выберите статью выбытия:"
MSG_SELECT_WALLET_OR_CREDITOR = "Выберите кошелёк для выбытия или кредитора:"


def _out_src_kb() -> InlineKeyboardBuilder:
    """Клавиатура для выбора источника выбытия (кошелек или кредитор)."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🏦 Кошелёк", callback_data="out_src:wallet"),
        InlineKeyboardButton(text="🤝 Кредитор", callback_data="out_src:creditor"),
    )
    return kb.as_markup()


async def _show_dict_kb(cb: CallbackQuery, state: FSMContext, builder: Callable, next_state: OperationState) -> tuple[
    str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру справочников (кошельки / кредиторы / проекты)."""
    async with get_async_session() as session:
        kb = await builder(session, state=state)

    await state.set_state(next_state)
    return MSG_SELECT_WALLET_OR_CREDITOR, kb


async def _get_choose_outcome_source_message() -> tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора источника выбытия."""
    kb = _out_src_kb()
    return MSG_INDICATE_OUTCOME_SOURCE, kb


def _outcome_chapter_kb() -> InlineKeyboardBuilder:
    """Клавиатура выбора категории выбытия."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=PROJECT_LABEL, callback_data="outcome_chapter:project"),
        InlineKeyboardButton(text=GENERAL_LABEL, callback_data="outcome_chapter:general"),
    )
    return kb.as_markup()


async def _get_choose_project_message(cb: CallbackQuery, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора проекта."""
    async with get_async_session() as session:
        kb = await create_project_keyboard(session, state=state)

    return MSG_CHOOSE_OUTCOME_PROJECT, kb


async def _get_choose_general_type_message(cb: CallbackQuery, state: FSMContext) -> tuple[str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора типа общих операций."""
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=FINANCE_LABEL, callback_data="general_type:finance"),
    )
    kb.row(
        InlineKeyboardButton(text=PAYROLL_LABEL, callback_data="general_type:payroll"),
    )
    kb.row(InlineKeyboardButton(text=BACK_LABEL, callback_data="nav:back"))
    return MSG_CHOOSE_OUTCOME_GENERAL_TYPE, kb.as_markup()


async def _get_choose_outcome_article_message(cb: CallbackQuery, state: FSMContext) -> tuple[
    str, InlineKeyboardBuilder]:
    """Возвращает текст и клавиатуру для выбора статьи выбытия."""
    async with get_async_session() as session:
        kb = await create_article_keyboard(session, state=state)

    return MSG_CHOOSE_OUTCOME_ARTICLE, kb


# ────────────────────── OUTCOME: WALLET vs CREDITOR ─────────────────────
@router.callback_query(F.data == "out_src:wallet", OperationState.choosing_outcome_wallet_or_creditor)
@track_messages
async def outcome_source_wallet(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    text, kb = await _show_dict_kb(cb, state, create_wallet_keyboard, OperationState.choosing_outcome_wallet)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "out_src:creditor", OperationState.choosing_outcome_wallet_or_creditor)
@track_messages
async def outcome_source_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    text, kb = await _show_dict_kb(cb, state, create_creditor_keyboard, OperationState.choosing_outcome_creditor)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


# ────────────────────── CHOOSE OUTCOME WALLET ─────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_outcome_wallet)
@track_messages
async def choose_outcome_wallet(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    log.info(f"User {cb.from_user.id}: Выбран кошелёк={cb.data}")
    wallet_id = cb.data.split(":")[1]
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)
    await state.update_data(outcome_wallet=wallet_id,
                            state_history=[OperationState.choosing_outcome_wallet_or_creditor.state])
    log.info(f"User {cb.from_user.id}: Выбран кошелёк={wallet.wallet_number}")
    text, kb = MSG_CHOOSE_OUTCOME_CHAPTER, _outcome_chapter_kb()
    await cb.message.edit_text(f"✅ Выбран кошелёк: <b>{wallet.wallet_number}</b>\n{text}", reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_chapter)
    await cb.answer()


# ────────────────────── CHOOSE OUTCOME CREDITOR ─────────────────────
@router.callback_query(CreditorCallback.filter(), OperationState.choosing_outcome_creditor)
@track_messages
async def choose_outcome_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    creditor_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран кредитор={creditor_id}")
    async with get_async_session() as session:
        creditor = await get_creditor(session, creditor_id)
    await state.update_data(outcome_creditor=creditor_id,
                            state_history=[OperationState.choosing_outcome_wallet_or_creditor.state])
    log.info(f"User {cb.from_user.id}: Выбран кредитор={creditor.name}")
    text, kb = MSG_CHOOSE_OUTCOME_CHAPTER, _outcome_chapter_kb()
    await cb.message.edit_text(f"✅ Выбран кредитор: <b>{creditor.name}</b>\n{text}", reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_chapter)
    await cb.answer()


# ───────────────────── CHOOSE OUTCOME CHAPTER ─────────────────────
@router.callback_query(OperationState.choosing_outcome_chapter)
@track_messages
async def choose_outcome_chapter(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = cb.data.split(":")[1]
    history = await state.get_data()
    history["state_history"].append(OperationState.choosing_outcome_chapter.state)
    await state.update_data(state_history=history["state_history"])
    if data == "project":
        lable = PROJECT_LABEL
        text, kb = await _get_choose_project_message(cb, state)
        await state.set_state(OperationState.choosing_outcome_project)
    elif data == "general":
        lable = GENERAL_LABEL
        text, kb = await _get_choose_general_type_message(cb, state)
        await state.set_state(OperationState.choosing_outcome_general_type)
    else:
        raise ValueError(f"Unknown outcome_chapter: {data}")
    data = await state.get_data()
    outcome_wallet = data.get("outcome_wallet")
    outcome_creditor = data.get("outcome_creditor")
    base_text = f"✅ Выбрана категория: <b>{lable}</b>\n{text}"
    if outcome_wallet:
        async with get_async_session() as session:
            wallet = await get_wallet(session, outcome_wallet)
            base_text = f"✅ Выбран кошелёк: <b>{wallet.wallet_number}</b>\n{base_text}"
    elif outcome_creditor:
        async with get_async_session() as session:
            creditor = await get_creditor(session, outcome_creditor)
            base_text = f"✅ Выбран кредитор: <b>{creditor.name}</b>\n{base_text}"
    await cb.message.edit_text(base_text, reply_markup=kb)
    await cb.answer()


# ───────────────────── CHOOSE OUTCOME PROJECT ─────────────────────
@router.callback_query(OperationState.choosing_outcome_project)
@track_messages
async def set_outcome_project(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    project_id = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        project = await get_project(session, project_id)
    history = await state.get_data()
    history["state_history"].append(OperationState.choosing_outcome_project.state)
    await state.update_data(state_history=history["state_history"], outcome_chapter=project_id)

    log.info(f"User {cb.from_user.id}: Выбран проект={project.name}")

    text, kb = await _get_choose_outcome_article_message(cb, state)
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_article)
    await cb.answer()


# ───────────────────── CHOOSE OUTCOME GENERAL TYPE ────────────────
@router.callback_query(OperationState.choosing_outcome_general_type)
@track_messages
async def choose_outcome_general_type(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    general_type = cb.data.split(":")[1]
    history = await state.get_data()
    history["state_history"].append(OperationState.choosing_outcome_general_type.state)
    await state.update_data(state_history=history["state_history"], outcome_general_type=general_type)
    log.info(f"User {cb.from_user.id}: Выбран тип общих операций={general_type}")
    text, kb = await _get_choose_outcome_article_message(cb, state)
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_article)
    await cb.answer()