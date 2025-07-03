# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/outcome_articles.py
"""Роутер выбора статей выбытия и связанных сущностей."""

from __future__ import annotations

from typing import Final, Callable, Tuple

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from src.bot.keyboards.article_kb import ArticleCallback
from src.bot.keyboards.contractor_kb import ContractorCallback, create_contractor_keyboard
from src.bot.keyboards.creditor_kb import CreditorCallback, create_creditor_keyboard
from src.bot.keyboards.employee_kb import EmployeeCallback, create_employee_keyboard
from src.bot.keyboards.founder_kb import FounderCallback, create_founder_keyboard
from src.bot.keyboards.material_kb import MaterialCallback, create_material_keyboard
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import (
    get_async_session,
    get_article,
    get_contractor,
    get_creditor,
    get_employee,
    get_founder,
    get_material,
    get_project,
    get_wallet,
)

router: Final = Router()
log = configure_logger(prefix="OUT_ART", color="magenta", level="INFO")

# ────────────────────────────── ТЕКСТЫ ────────────────────────────────
EMO_WALLET    = "🏦"
EMO_CREDITOR  = "🤝"
EMO_PROJECT   = "🗂️"
EMO_GENERAL   = "📂"
EMO_ARTICLE   = "📄"
EMO_CONTRACT  = "👷"
EMO_MATERIAL  = "🧱"
EMO_EMPLOYEE  = "👤"
EMO_FOUNDER   = "🏢"
EMO_AMOUNT    = "💰"

MSG_CHOOSE_CONTRACTOR = "Выберите бригаду или подрядчика:"
MSG_CHOOSE_MATERIAL   = "Выберите материал:"
MSG_CHOOSE_EMPLOYEE   = "Выберите сотрудника:"
MSG_CHOOSE_CREDITOR   = "Выберите кредитора:"
MSG_CHOOSE_FOUNDER    = "Выберите учредителя:"
MSG_ENTER_AMOUNT      = f"{EMO_AMOUNT} Введите сумму операции:"

PROJECT_LABEL = "По проектам"
GENERAL_LABEL = "Общие"

# ─────────────────────────── ПОМОЩНИКИ UI ──────────────────────────────
async def _show_dict_kb(
    cb: CallbackQuery,
    state: FSMContext,
    builder: Callable,
    next_state: OperationState,
    prompt: str,
) -> None:
    """Показ справочника (подрядчики, материалы …)."""
    async with get_async_session() as session:
        kb = await builder(session, state=state)
    await state.set_state(next_state)
    await cb.message.edit_text(prompt, reply_markup=kb)
    await cb.answer()

async def _build_outcome_summary(state: FSMContext) -> str:
    """Красочная сводка сделанных выборов."""
    data = await state.get_data()
    lines: list[str] = []

    async with get_async_session() as session:
        if wid := data.get("outcome_wallet"):
            wallet = await get_wallet(session, wid)
            lines.append(f"{EMO_WALLET} Кошелёк: <b>{wallet.wallet_number}</b>")
        elif cid := data.get("outcome_creditor"):
            cred = await get_creditor(session, cid)
            lines.append(f"{EMO_CREDITOR} Кредитор: <b>{cred.name}</b>")

        if proj_id := data.get("outcome_chapter"):
            proj = await get_project(session, proj_id)
            lines.append(f"{EMO_PROJECT} Категория: <b>{PROJECT_LABEL}</b>")
            lines.append(f"  {EMO_PROJECT} Проект: <b>{proj.name}</b>")
        elif gt := data.get("outcome_general_type"):
            lines.append(f"{EMO_GENERAL} Категория: <b>{GENERAL_LABEL}</b>")

        if art_id := data.get("outcome_article"):
            art = await get_article(session, art_id)
            art_name = art.name if art else str(art_id)
            lines.append(f"{EMO_ARTICLE} Статья: <b>{art_name}</b>")

        # детализаторы статьи
        if con_id := data.get("contractor_id"):
            contr = await get_contractor(session, con_id)
            lines.append(f"{EMO_CONTRACT} Подрядчик: <b>{contr.name}</b>")
        if mat_id := data.get("material_id"):
            mat = await get_material(session, mat_id)
            lines.append(f"{EMO_MATERIAL} Материал: <b>{mat.name}</b>")
        if emp_id := data.get("employee_id"):
            emp = await get_employee(session, emp_id)
            lines.append(f"{EMO_EMPLOYEE} Сотрудник: <b>{emp.name}</b>")
        if art_cred := data.get("outcome_article_creditor"):
            lines.append(f"{EMO_CREDITOR} Кредитор: <b>{art_cred}</b>")
        if founder_id := data.get("outcome_founder_id"):
            founder = await get_founder(session, founder_id)
            lines.append(f"{EMO_FOUNDER} Учредитель: <b>{founder.name}</b>")

    return "\n".join(lines)

async def _proceed_to_amount(
    cb: CallbackQuery,
    state: FSMContext,
    summary_text: str | None = None,
) -> None:
    """Переход к вводу суммы: выводим сводку и спрашиваем сумму."""
    await state.set_state(OperationState.entering_operation_amount)

    if summary_text is None:
        summary_text = await _build_outcome_summary(state)

    if summary_text:
        msg = await cb.message.edit_text(summary_text, parse_mode="HTML")
        await state.update_data(summary_message_id=msg.message_id)

    amt_msg = await cb.message.bot.send_message(cb.message.chat.id, MSG_ENTER_AMOUNT)
    await state.update_data(amount_message_id=amt_msg.message_id)
    await cb.answer()

# ─────────────────────── ВЫБОР СТАТЬИ ────────────────────────────────
@router.callback_query(ArticleCallback.filter(), OperationState.choosing_outcome_article)
@track_messages
async def choose_outcome_article(
    cb: CallbackQuery,
    state: FSMContext,
    bot: Bot,  # noqa: ARG001
) -> None:
    article_id = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        art = await get_article(session, article_id)

    await state.update_data(outcome_article=article_id)
    log.info(
        f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбрана статья – "
        f"{art.name if art else article_id} (ID {article_id})"
    )

    summary = await _build_outcome_summary(state)

    match article_id:
        case 3:
            await _show_dict_kb(cb, state, create_contractor_keyboard,
                                OperationState.choosing_contractor,
                                f"{summary}\n\n{MSG_CHOOSE_CONTRACTOR}")
            await state.update_data(contractor_id=None)
        case 4:
            await _show_dict_kb(cb, state, create_material_keyboard,
                                OperationState.choosing_material,
                                f"{summary}\n\n{MSG_CHOOSE_MATERIAL}")
            await state.update_data(material_id=None)
        case 7 | 8 | 11:
            await _show_dict_kb(cb, state, create_employee_keyboard,
                                OperationState.choosing_employee,
                                f"{summary}\n\n{MSG_CHOOSE_EMPLOYEE}")
            await state.update_data(employee_id=None)
        case 29:
            await _show_dict_kb(cb, state, create_creditor_keyboard,
                                OperationState.choosing_creditor,
                                f"{summary}\n\n{MSG_CHOOSE_CREDITOR}")
            await state.update_data(outcome_article_creditor=None)
        case 30:
            await _show_dict_kb(cb, state, create_founder_keyboard,
                                OperationState.choosing_founder,
                                f"{summary}\n\n{MSG_CHOOSE_FOUNDER}")
            await state.update_data(outcome_founder_id=None)
        case _:
            await _proceed_to_amount(cb, state, summary)

# ─────────────────────── ВЫБОР ПОДРЯДЧИКА ───────────────────────────
@router.callback_query(ContractorCallback.filter(), OperationState.choosing_contractor)
@track_messages
async def choose_contractor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cid = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        contr = await get_contractor(session, cid)

    await state.update_data(contractor_id=cid)
    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбран подрядчик – {contr.name} (ID {cid})")

    await _proceed_to_amount(cb, state)

# ─────────────────────── ВЫБОР МАТЕРИАЛА ────────────────────────────
@router.callback_query(MaterialCallback.filter(), OperationState.choosing_material)
@track_messages
async def choose_material(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    mid = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        mat = await get_material(session, mid)

    await state.update_data(material_id=mid)
    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбран материал – {mat.name} (ID {mid})")

    await _proceed_to_amount(cb, state)

# ─────────────────────── ВЫБОР СОТРУДНИКА ────────────────────────────
@router.callback_query(EmployeeCallback.filter(), OperationState.choosing_employee)
@track_messages
async def choose_employee(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    eid = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        emp = await get_employee(session, eid)

    await state.update_data(employee_id=eid)
    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбран сотрудник – {emp.name} (ID {eid})")

    await _proceed_to_amount(cb, state)

# ─────────────────────── ВЫБОР КРЕДИТОРА ────────────────────────────
@router.callback_query(CreditorCallback.filter(), OperationState.choosing_creditor)
@track_messages
async def choose_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cid = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        cred = await get_creditor(session, cid)

    await state.update_data(outcome_article_creditor=cred.name)
    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбран кредитор – {cred.name} (ID {cid})")

    await _proceed_to_amount(cb, state)

# ─────────────────────── ВЫБОР УЧРЕДИТЕЛЯ ────────────────────────────
@router.callback_query(FounderCallback.filter(), OperationState.choosing_founder)
@track_messages
async def choose_founder(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    fid = int(cb.data.split(":")[1])
    async with get_async_session() as session:
        founder = await get_founder(session, fid)

    await state.update_data(outcome_founder_id=fid)
    log.info(f"Юзер {cb.from_user.full_name} ({cb.from_user.id}): выбран учредитель – {founder.name} (ID {fid})")

    await _proceed_to_amount(cb, state)
