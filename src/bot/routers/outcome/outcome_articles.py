# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/outcome/outcome_articles.py
"""
Роутер для обработки выбора статей выбытия.
"""

from __future__ import annotations

from typing import Final, Callable

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot.keyboards.article_kb import ArticleCallback
from src.bot.keyboards.contractor_kb import ContractorCallback, create_contractor_keyboard
from src.bot.keyboards.creditor_kb import CreditorCallback, create_creditor_keyboard
from src.bot.keyboards.employee_kb import EmployeeCallback, create_employee_keyboard
from src.bot.keyboards.founder_kb import FounderCallback, create_founder_keyboard
from src.bot.keyboards.material_kb import MaterialCallback, create_material_keyboard
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import track_messages
from src.core.logger import configure_logger
from src.db import get_async_session, get_contractor, get_material, get_employee, get_creditor, get_founder, get_wallet, get_project, get_article

router: Final = Router()
log = configure_logger(prefix="OUTCOME_ARTICLES", color="magenta", level="INFO")

# ─────────────────────────── CONSTANTS ─────────────────────────────
MSG_CHOOSE_BRIGADE_CONTRACTOR = "Выберите бригаду или подрядчика:"
MSG_CHOOSE_MATERIAL = "Выберите материал:"
MSG_CHOOSE_EMPLOYEE = "Выберите сотрудника:"
MSG_CHOOSE_CREDITOR = "Выберите кредитора:"
MSG_CHOOSE_FOUNDER = "Выберите учредителя:"
MSG_ENTER_AMOUNT = "Введите сумму операции:"
PROJECT_LABEL = "📋 По проектам"
GENERAL_LABEL = "🌐 Общие"


# ──────────────────────────── HELPERS ──────────────────────────────
async def _show_dict_kb(cb: CallbackQuery, state: FSMContext, builder: Callable, next_state: OperationState,
                        message: str) -> None:
    """Возвращает текст и клавиатуру для справочников (бригады, подрядчики, материалы, сотрудники, кредиторы, учредители)."""
    async with get_async_session() as session:
        kb = await builder(session, state=state)

    await state.set_state(next_state)
    await cb.message.edit_text(message, reply_markup=kb)
    await cb.answer()

    return message, kb


async def _build_outcome_summary(state: FSMContext) -> str:
    """Формирует сводку предыдущих выборов."""
    data = await state.get_data()
    outcome_wallet = data.get("outcome_wallet")
    outcome_creditor = data.get("outcome_creditor")
    outcome_chapter = data.get("outcome_chapter")
    outcome_general_type = data.get("outcome_general_type")
    contractor_id = data.get("contractor_id")
    material_id = data.get("material_id")
    employee_id = data.get("employee_id")
    outcome_article_creditor = data.get("outcome_article_creditor")
    outcome_founder_id = data.get("outcome_founder_id")
    outcome_article = data.get("outcome_article")

    summary = ""
    if outcome_wallet:
        async with get_async_session() as session:
            wallet = await get_wallet(session, outcome_wallet)
            summary += f"✅ Выбран кошелёк: <b>{wallet.wallet_number}</b>\n"
    elif outcome_creditor:
        async with get_async_session() as session:
            creditor = await get_creditor(session, outcome_creditor)
            summary += f"✅ Выбран кредитор: <b>{creditor.name}</b>\n"

    if outcome_chapter:
        async with get_async_session() as session:
            project = await get_project(session, outcome_chapter)
            summary += f"✅ Выбрана категория: <b>{PROJECT_LABEL}</b>\n✅ Выбран проект: <b>{project.name}</b>\n"
    elif outcome_general_type:
        summary += f"✅ Выбрана категория: <b>{GENERAL_LABEL}</b>\n✅ Выбран тип общих операций: <b>{outcome_general_type.capitalize()}</b>\n"

    if outcome_article:
        async with get_async_session() as session:
            article = await get_article(session, outcome_article)
            article_name = article.name if article else str(outcome_article)
            if contractor_id:
                contractor = await get_contractor(session, contractor_id)
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n✅ Выбран подрядчик: <b>{contractor.name if contractor else contractor_id}</b>\n"
            elif material_id:
                material = await get_material(session, material_id)
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n✅ Выбран материал: <b>{material.name if material else material_id}</b>\n"
            elif employee_id:
                employee = await get_employee(session, employee_id)
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n✅ Выбран сотрудник: <b>{employee.name if employee else employee_id}</b>\n"
            elif outcome_article_creditor:
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n✅ Выбран кредитор: <b>{outcome_article_creditor}</b>\n"
            elif outcome_founder_id:
                founder = await get_founder(session, outcome_founder_id)
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n✅ Выбран учредитель: <b>{founder.name if founder else outcome_founder_id}</b>\n"
            else:
                summary += f"✅ Выбрана статья: <b>{article_name}</b>\n"

    return summary


async def _proceed_to_amount(cb: CallbackQuery, state: FSMContext, summary_text: str = None) -> None:
    """Переход к вводу суммы с отдельным сообщением для сводки."""
    await state.set_state(OperationState.entering_operation_amount)

    # Отправляем сводку как отдельное сообщение
    if summary_text is None:
        summary_text = await _build_outcome_summary(state)
    if summary_text:
        summary_message = await cb.message.edit_text(text=summary_text, parse_mode="HTML")
        await state.update_data(summary_message_id=summary_message.message_id)

    # Отправляем запрос суммы как отдельное сообщение
    amount_message = await cb.message.bot.send_message(chat_id=cb.message.chat.id, text=MSG_ENTER_AMOUNT)
    await state.update_data(amount_message_id=amount_message.message_id)

    await cb.answer()


# ────────────────────── CHOOSE OUTCOME ARTICLE ─────────────────────
@router.callback_query(ArticleCallback.filter(), OperationState.choosing_outcome_article)
@track_messages
async def choose_outcome_article(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    article_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбрана статья={article_id}")

    await state.update_data(outcome_article=article_id)  # Сохраняем article_id
    summary = await _build_outcome_summary(state)
    if article_id == 3:
        await _show_dict_kb(cb, state, create_contractor_keyboard, OperationState.choosing_contractor,
                            f"{summary}{MSG_CHOOSE_BRIGADE_CONTRACTOR}")
        await state.update_data(contractor_id=None)
    elif article_id == 4:
        await _show_dict_kb(cb, state, create_material_keyboard, OperationState.choosing_material,
                            f"{summary}{MSG_CHOOSE_MATERIAL}")
        await state.update_data(material_id=None)
    elif article_id in {7, 8, 11}:
        await _show_dict_kb(cb, state, create_employee_keyboard, OperationState.choosing_employee,
                            f"{summary}{MSG_CHOOSE_EMPLOYEE}")
        await state.update_data(employee_id=None)
    elif article_id == 29:
        await _show_dict_kb(cb, state, create_creditor_keyboard, OperationState.choosing_creditor,
                            f"{summary}{MSG_CHOOSE_CREDITOR}")
        await state.update_data(outcome_article_creditor=None, outcome_founder_id=None)
    elif article_id == 30:
        await _show_dict_kb(cb, state, create_founder_keyboard, OperationState.choosing_founder,
                            f"{summary}{MSG_CHOOSE_FOUNDER}")
        await state.update_data(outcome_founder_id=None)
    else:
        await _proceed_to_amount(cb, state, summary)


# ────────────────────── CHOOSE CONTRACTOR ─────────────────────
@router.callback_query(ContractorCallback.filter(), OperationState.choosing_contractor)
@track_messages
async def choose_contractor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    contractor_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран подрядчик ID={contractor_id}")
    await state.update_data(contractor_id=contractor_id)
    summary = await _build_outcome_summary(state)
    await _proceed_to_amount(cb, state, summary)


# ────────────────────── CHOOSE MATERIAL ─────────────────────
@router.callback_query(MaterialCallback.filter(), OperationState.choosing_material)
@track_messages
async def choose_material(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    material_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран материал ID={material_id}")
    await state.update_data(material_id=material_id)
    summary = await _build_outcome_summary(state)
    await _proceed_to_amount(cb, state, summary)


# ────────────────────── CHOOSE EMPLOYEE ─────────────────────
@router.callback_query(EmployeeCallback.filter(), OperationState.choosing_employee)
@track_messages
async def choose_employee(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    employee_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран сотрудник ID={employee_id}")
    await state.update_data(employee_id=employee_id)
    summary = await _build_outcome_summary(state)
    await _proceed_to_amount(cb, state, summary)


# ────────────────────── CHOOSE CREDITOR ─────────────────────
@router.callback_query(CreditorCallback.filter(), OperationState.choosing_creditor)
@track_messages
async def choose_creditor(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    creditor_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран кредитор ID={creditor_id}")
    async with get_async_session() as session:
        creditor = await get_creditor(session, creditor_id)
    await state.update_data(outcome_article_creditor=creditor.name, outcome_founder_id=None)
    summary = await _build_outcome_summary(state)
    await _proceed_to_amount(cb, state, summary)


# ────────────────────── CHOOSE FOUNDER ─────────────────────
@router.callback_query(FounderCallback.filter(), OperationState.choosing_founder)
@track_messages
async def choose_founder(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    founder_id = int(cb.data.split(":")[1])
    log.info(f"User {cb.from_user.id}: Выбран учредитель ID={founder_id}")
    await state.update_data(outcome_founder_id=founder_id)
    summary = await _build_outcome_summary(state)
    await _proceed_to_amount(cb, state, summary)