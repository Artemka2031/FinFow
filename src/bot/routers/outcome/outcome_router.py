# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/outcome_router.py
"""Роутер обработки операций «Выбытие»."""

from __future__ import annotations

from typing import Final, Callable, Tuple

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.keyboards.article_kb import create_article_keyboard
from src.bot.keyboards.creditor_kb import CreditorCallback, create_creditor_keyboard
from src.bot.keyboards.project_kb import create_project_keyboard, ProjectCallback
from src.bot.keyboards.wallet_kb import WalletCallback, create_wallet_keyboard
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_wallet, get_creditor, get_project

# ───────────────────────────── КОНСТАНТЫ UI ─────────────────────────────
EMOJI_WALLET:   Final = "🏦"
EMOJI_CREDITOR: Final = "🤝"
EMOJI_FOLDER:   Final = "📑"

MSG_INDICATE_SOURCE  : Final = "Укажите источник выбытия:"
MSG_CHOOSE_CHAPTER   : Final = f"{EMOJI_FOLDER} Выберите категорию выбытия:"
MSG_CHOOSE_PROJECT   : Final = "Выберите <b>Проект</b>:"
MSG_CHOOSE_GENERAL   : Final = "Выберите тип общих операций:"
MSG_CHOOSE_ARTICLE   : Final = f"{EMOJI_FOLDER} Выберите статью выбытия:"
MSG_SELECT_DICT      : Final = "Выберите кошелёк для выбытия или кредитора:"

PROJECT_LABEL  = "📋 По проектам"
GENERAL_LABEL  = "🌐 Общие"
FINANCE_LABEL  = "💰 Фин. операции и инвестиции"
PAYROLL_LABEL  = "👥 ФОТ и другое"
BACK_LABEL     = "⬅️ Назад"

# ──────────────────────────── РОУТЕР/ЛОГ ───────────────────────────────
router: Final = Router()
log = configure_logger(prefix="OUTCOME", color="red", level="INFO")

# ──────────────────────────── КЛАВИАТУРЫ ───────────────────────────────
def _kb_source() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=f"{EMOJI_WALLET} Кошелёк",   callback_data="out_src:wallet"),
        InlineKeyboardButton(text=f"{EMOJI_CREDITOR} Кредитор", callback_data="out_src:creditor"),
    )
    return kb.as_markup()


def _kb_chapter() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text=PROJECT_LABEL, callback_data="outcome_chapter:project"),
        InlineKeyboardButton(text=GENERAL_LABEL, callback_data="outcome_chapter:general"),
    )
    return kb.as_markup()


def _kb_general_types() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text=FINANCE_LABEL, callback_data="general_type:finance"))
    kb.row(InlineKeyboardButton(text=PAYROLL_LABEL, callback_data="general_type:payroll"))
    kb.row(InlineKeyboardButton(text=BACK_LABEL,    callback_data="nav:back"))
    return kb.as_markup()

# ────────────────────────── HELPERS (TEXT+KB) ───────────────────────────
async def _dict_kb(
    state: FSMContext,
    builder_fn: Callable,
    next_state: OperationState,
) -> Tuple[str, InlineKeyboardMarkup]:
    """Возвращает текст + клавиатуру справочника и переводит в next_state."""
    async with get_async_session() as session:
        kb_builder = await builder_fn(session, state=state)
    await state.set_state(next_state)
    return MSG_SELECT_DICT, kb_builder


async def _msg_choose_project(state: FSMContext) -> Tuple[str, InlineKeyboardMarkup]:
    async with get_async_session() as session:
        kb_builder = await create_project_keyboard(session, state=state)
    return MSG_CHOOSE_PROJECT, kb_builder


async def _msg_choose_general_type() -> Tuple[str, InlineKeyboardMarkup]:
    return MSG_CHOOSE_GENERAL, _kb_general_types()


async def _msg_choose_article(state: FSMContext) -> Tuple[str, InlineKeyboardMarkup]:
    async with get_async_session() as session:
        kb_builder = await create_article_keyboard(session, state=state)
    return MSG_CHOOSE_ARTICLE, kb_builder

# ─────────────────── WALLET / CREDITOR ИСТОЧНИК ─────────────────────────
@router.callback_query(F.data == "out_src:wallet", OperationState.choosing_outcome_wallet_or_creditor)
@track_messages
async def outcome_src_wallet(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    text, kb = await _dict_kb(state, create_wallet_keyboard, OperationState.choosing_outcome_wallet)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "out_src:creditor", OperationState.choosing_outcome_wallet_or_creditor)
@track_messages
async def outcome_src_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    text, kb = await _dict_kb(state, create_creditor_keyboard, OperationState.choosing_outcome_creditor)
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ────────────────────────── ВЫБОР КОШЕЛЬКА ──────────────────────────────
@router.callback_query(WalletCallback.filter(), OperationState.choosing_outcome_wallet)
@track_messages
async def choose_outcome_wallet(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    wallet_id = cb.data.split(":")[1]
    async with get_async_session() as session:
        wallet = await get_wallet(session, wallet_id)

    await state.update_data(
        outcome_wallet=wallet_id,
        state_history=[OperationState.choosing_outcome_wallet_or_creditor.state],
    )
    log.info(f"Юзер {cb.from_user.full_name}: выбран wallet – {wallet.wallet_number}")

    text, kb = MSG_CHOOSE_CHAPTER, _kb_chapter()
    await cb.message.edit_text(
        f"✅ Выбран кошелёк: <b>{wallet.wallet_number}</b>\n{text}",
        reply_markup=kb,
    )
    await state.set_state(OperationState.choosing_outcome_chapter)
    await cb.answer()

# ────────────────────────── ВЫБОР КРЕДИТОРА ─────────────────────────────
@router.callback_query(CreditorCallback.filter(), OperationState.choosing_outcome_creditor)
@track_messages
async def choose_outcome_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    creditor_id = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        creditor = await get_creditor(session, creditor_id)

    await state.update_data(
        outcome_creditor=creditor_id,
        state_history=[OperationState.choosing_outcome_wallet_or_creditor.state],
    )
    log.info(f"Юзер {cb.from_user.full_name}: выбран creditor – {creditor.name}")

    text, kb = MSG_CHOOSE_CHAPTER, _kb_chapter()
    await cb.message.edit_text(
        f"✅ Выбран кредитор: <b>{creditor.name}</b>\n{text}",
        reply_markup=kb,
    )
    await state.set_state(OperationState.choosing_outcome_chapter)
    await cb.answer()

# ──────────────────────── ВЫБОР КАТЕГОРИИ ───────────────────────────────
@router.callback_query(OperationState.choosing_outcome_chapter)
@track_messages
async def choose_outcome_chapter(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    chapter = cb.data.split(":")[1]
    hist = (await state.get_data()).get("state_history", [])
    hist.append(OperationState.choosing_outcome_chapter.state)
    await state.update_data(state_history=hist)

    if chapter == "project":
        label = PROJECT_LABEL
        text, kb = await _msg_choose_project(state)
        next_state = OperationState.choosing_outcome_project
    elif chapter == "general":
        label = GENERAL_LABEL
        text, kb = await _msg_choose_general_type()
        next_state = OperationState.choosing_outcome_general_type
    else:
        raise ValueError(f"Unknown outcome_chapter: {chapter}")

    # Добавляем выбранный источник в заголовок
    data = await state.get_data()
    prefix = ""
    if data.get("outcome_wallet"):
        async with get_async_session() as session:
            wallet = await get_wallet(session, data["outcome_wallet"])
        prefix = f"✅ Выбран кошелёк: <b>{wallet.wallet_number}</b>\n"
    elif data.get("outcome_creditor"):
        async with get_async_session() as session:
            creditor = await get_creditor(session, data["outcome_creditor"])
        prefix = f"✅ Выбран кредитор: <b>{creditor.name}</b>\n"

    await cb.message.edit_text(f"{prefix}✅ Выбрана категория: <b>{label}</b>\n{text}", reply_markup=kb)
    await state.set_state(next_state)
    await cb.answer()

# ────────────────────────── ВЫБОР ПРОЕКТА ───────────────────────────────
@router.callback_query(ProjectCallback.filter(), OperationState.choosing_outcome_project)
@track_messages
async def set_outcome_project(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    project_id = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        project = await get_project(session, project_id)

    hist = (await state.get_data()).get("state_history", [])
    hist.append(OperationState.choosing_outcome_project.state)
    await state.update_data(state_history=hist, outcome_chapter=project_id)

    log.info(f"Юзер {cb.from_user.full_name}: выбран project – {
    project.name}")

    text, kb = await _msg_choose_article(state)
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_article)
    await cb.answer()

# ─────────────────────── ВЫБОР ОБЩЕГО ТИПА ──────────────────────────────
@router.callback_query(OperationState.choosing_outcome_general_type)
@track_messages
async def choose_outcome_general_type(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    g_type = cb.data.split(":")[1]

    hist = (await state.get_data()).get("state_history", [])
    hist.append(OperationState.choosing_outcome_general_type.state)
    await state.update_data(state_history=hist, outcome_general_type=g_type)

    log.info(f"Юзер {cb.from_user.full_name}: выбран general_type – {g_type}")

    text, kb = await _msg_choose_article(state)
    await cb.message.edit_text(text, reply_markup=kb)
    await state.set_state(OperationState.choosing_outcome_article)
    await cb.answer()
