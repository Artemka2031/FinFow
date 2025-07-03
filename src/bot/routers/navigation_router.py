# -*- coding: utf-8 -*-
# FinFlow/src/bot/routers/navigation_router.py
"""
Роутер для обработки навигации, включая кнопку «Назад».
"""

from __future__ import annotations

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
)

from src.bot.keyboards import create_creditor_keyboard, create_wallet_keyboard
from src.bot.routers.date_type_router import (
    _get_choose_operation_date_message,
    _get_choose_operation_type_message,
    _dict_kb,
)
from src.bot.routers.income.income_router import (
    _choose_income_wallet_msg,
    _choose_income_article_msg,
)
from src.bot.routers.outcome.outcome_router import (
    _msg_choose_project as get_choose_outcome_project_message,
    _msg_choose_general_type as get_choose_outcome_general_type_message,
    _msg_choose_article,
    MSG_INDICATE_SOURCE, _kb_source, MSG_CHOOSE_CHAPTER, _kb_chapter,
)
from src.bot.routers.transfer.transfer_router import (
    _get_choose_from_wallet_message,
    _get_choose_to_wallet_message,
)
from src.bot.state import OperationState
from src.bot.utils.legacy_messages import delete_key_messages, delete_tracked_messages
from src.core.logger import configure_logger

# ──────────────────────────── HELPERS ──────────────────────────────

router = Router()
log = configure_logger(prefix="NAV", color="blue", level="INFO")


@router.callback_query(lambda cb: cb.data == "nav:back")
async def process_back_navigation(cb: CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает нажатие кнопки «Назад»."""

    data = await state.get_data()
    state_history: list[str] = data.get("state_history", [])
    if not state_history:
        await cb.answer("Нет предыдущего состояния для возврата.")
        return

    await delete_tracked_messages(bot, state, cb.message.chat.id)
    await delete_key_messages(bot, state, cb.message.chat.id, exclude_message_ids=[
        data.get("type_message_id"),
        data.get("income_wallet_message_id"),
        data.get("article_message_id"),
        data.get("outcome_source_message_id"),
        data.get("chapter_message_id"),
        data.get("project_message_id"),
        data.get("general_type_message_id"),
    ])

    prev_state = state_history.pop()
    current_state = await state.get_state()

    if current_state == OperationState.choosing_to_wallet.state:
        await state.update_data(to_wallet=None)
    elif current_state == OperationState.entering_operation_amount.state:
        await state.update_data(operation_amount=None)
    elif current_state in [
        OperationState.choosing_income_project.state,
        OperationState.choosing_income_creditor.state,
        OperationState.choosing_income_founder.state,
        OperationState.choosing_income_additional_info.state,
    ]:
        await state.update_data(income_project=None, income_creditor=None, income_founder=None,
                                income_additional_info=None)
    elif current_state == OperationState.choosing_income_wallet.state:
        await state.update_data(income_wallet=None)
    elif current_state == OperationState.choosing_income_article.state:
        await state.update_data(income_article=None)
    elif current_state == OperationState.choosing_outcome_project.state:
        await state.update_data(outcome_chapter=None)
    elif current_state == OperationState.choosing_outcome_general_type.state:
        await state.update_data(outcome_general_type=None)
    elif current_state == OperationState.choosing_outcome_article.state:
        await state.update_data(outcome_article=None)
    elif current_state == OperationState.entering_outcome_details.state:
        await state.update_data(employee_name=None, material_name=None, contractor_name=None,
                                outcome_article_creditor=None, outcome_founder=None)
    elif current_state == OperationState.choosing_outcome_wallet_or_creditor.state:
        await state.update_data(outcome_wallet=None, outcome_creditor=None)
    elif current_state == OperationState.choosing_outcome_wallet.state:
        await state.update_data(outcome_wallet=None)
    elif current_state == OperationState.choosing_outcome_creditor.state:
        await state.update_data(outcome_creditor=None)
    elif current_state == OperationState.choosing_contractor.state:
        await state.update_data(contractor_name=None)
    elif current_state == OperationState.choosing_material.state:
        await state.update_data(material_name=None)
    elif current_state == OperationState.choosing_employee.state:
        await state.update_data(employee_name=None)
    elif current_state == OperationState.choosing_creditor.state:
        await state.update_data(outcome_article_creditor=None)
    elif current_state == OperationState.choosing_founder.state:
        await state.update_data(outcome_founder=None)

    await state.update_data(state_history=state_history)
    await state.set_state(prev_state)

    if prev_state == OperationState.choosing_operation_date.state:
        text, kb = await _get_choose_operation_date_message(state)
        message_id = data.get("date_message_id")
    elif prev_state == OperationState.choosing_operation_type.state:
        text, kb = await _get_choose_operation_type_message()
        message_id = data.get("type_message_id")
    elif prev_state == OperationState.choosing_income_wallet.state:
        text, kb = await _choose_income_wallet_msg()
        message_id = data.get("income_wallet_message_id")
    elif prev_state == OperationState.choosing_income_article.state:
        text, kb = await _choose_income_article_msg(state)
        message_id = data.get("article_message_id")
    elif prev_state == OperationState.choosing_from_wallet.state:
        text, kb = await _get_choose_from_wallet_message(cb, state)
        message_id = None
    elif prev_state == OperationState.choosing_to_wallet.state:
        text, kb = await _get_choose_to_wallet_message(cb, state)
        message_id = None
    elif prev_state == OperationState.choosing_outcome_wallet_or_creditor.state:
        text, kb = MSG_INDICATE_SOURCE, _kb_source()
        message_id = data.get("outcome_source_message_id")
    elif prev_state == OperationState.choosing_outcome_wallet.state:
        text, kb = await _dict_kb(state, create_wallet_keyboard, OperationState.choosing_outcome_wallet)
        message_id = data.get("outcome_source_message_id")
    elif prev_state == OperationState.choosing_outcome_creditor.state:
        text, kb = await _dict_kb(state, create_creditor_keyboard, OperationState.choosing_outcome_creditor)
        message_id = data.get("outcome_source_message_id")
    elif prev_state == OperationState.choosing_outcome_chapter.state:
        text, kb = MSG_CHOOSE_CHAPTER, _kb_chapter()
        message_id = data.get("chapter_message_id")
    elif prev_state == OperationState.choosing_outcome_project.state:
        text, kb = await get_choose_outcome_project_message(state)
        message_id = data.get("project_message_id")
    elif prev_state == OperationState.choosing_outcome_general_type.state:
        text, kb = await get_choose_outcome_general_type_message()
        message_id = data.get("general_type_message_id")
    elif prev_state == OperationState.choosing_outcome_article.state:
        text, kb = await _msg_choose_article(state)
        message_id = data.get("article_message_id")
    elif prev_state in {OperationState.choosing_contractor.state, OperationState.choosing_material.state,
                        OperationState.choosing_employee.state, OperationState.choosing_creditor.state,
                        OperationState.choosing_founder.state}:
        text, kb = await _msg_choose_article(state)
        message_id = data.get("article_message_id")
    else:
        await cb.answer("Невозможно вернуться к этому состоянию.")
        return

    if message_id:
        try:
            await bot.edit_message_text(chat_id=cb.message.chat.id, message_id=message_id, text=text, reply_markup=kb,
                                        parse_mode="HTML")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await cb.answer("Клавиатура уже отображена.")
            elif "message to edit not found" in str(e):
                new_message = await bot.send_message(chat_id=cb.message.chat.id, text=text, reply_markup=kb,
                                                     parse_mode="HTML")
                if prev_state == OperationState.choosing_operation_date.state:
                    await state.update_data(date_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_operation_type.state:
                    await state.update_data(type_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_income_wallet.state:
                    await state.update_data(income_wallet_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_income_article.state:
                    await state.update_data(article_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_outcome_wallet_or_creditor.state:
                    await state.update_data(outcome_source_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_outcome_chapter.state:
                    await state.update_data(chapter_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_outcome_project.state:
                    await state.update_data(project_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_outcome_general_type.state:
                    await state.update_data(general_type_message_id=new_message.message_id)
                elif prev_state == OperationState.choosing_outcome_article.state:
                    await state.update_data(article_message_id=new_message.message_id)
                elif prev_state in {OperationState.choosing_contractor.state, OperationState.choosing_material.state,
                                    OperationState.choosing_employee.state, OperationState.choosing_creditor.state,
                                    OperationState.choosing_founder.state}:
                    await state.update_data(article_message_id=new_message.message_id)
            else:
                raise
    else:
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await cb.answer("Клавиатура уже отображена.")
            else:
                raise

    await cb.answer()