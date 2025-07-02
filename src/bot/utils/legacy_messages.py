# -*- coding: utf-8 -*-
# FinFlow/src/bot/utils/legacy_messages.py
from functools import wraps
from typing import Callable, Optional, List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot.state import OperationState
from src.core.logger import configure_logger

log = configure_logger(prefix="LEGACY_MSG", color="yellow", level="INFO")

# Мапа ключевых сообщений для каждого состояния
KEY_MESSAGE_FIELDS = {
    OperationState.choosing_operation_date: "date_message_id",
    OperationState.choosing_operation_type: "type_message_id",
    OperationState.choosing_income_wallet: "income_wallet_message_id",
    OperationState.choosing_income_article: "article_message_id",
    OperationState.choosing_income_project: "project_message_id",
    OperationState.choosing_income_creditor: "creditor_message_id",
    OperationState.choosing_income_founder: "founder_message_id",
    OperationState.choosing_income_additional_info: "additional_info_message_id",
    OperationState.choosing_from_wallet: "from_wallet_message_id",
    OperationState.choosing_to_wallet: "to_wallet_message_id",
    OperationState.choosing_outcome_wallet_or_creditor: "outcome_source_message_id",
    OperationState.choosing_outcome_chapter: "chapter_message_id",
    OperationState.choosing_outcome_project: "project_message_id",
    OperationState.choosing_outcome_general_type: "general_type_message_id",
    OperationState.choosing_outcome_article: "article_message_id",
    OperationState.choosing_contractor: "contractor_message_id",
    OperationState.choosing_material: "material_message_id",
    OperationState.choosing_employee: "employee_message_id",
    OperationState.choosing_creditor: "creditor_message_id",
    OperationState.choosing_founder: "founder_message_id",
    OperationState.entering_outcome_details: "details_message_id",
    OperationState.entering_operation_amount: "amount_message_id",  # Для запроса суммы
    OperationState.entering_operation_comment: "comment_message_id",
    OperationState.confirming_operation: "confirm_message_id",
}

# Дополнительный ключ для сводки
SUMMARY_MESSAGE_KEY = "summary_message_id"

# Список временных сообщений для удаления
TRACKING_KEY = "messages_to_delete"


async def delete_key_messages(
    bot: Bot,
    state: FSMContext,
    chat_id: int,
    exclude_message_id: Optional[int] = None,
    exclude_message_ids: Optional[List[int]] = None
) -> None:
    """Удаляет ключевые сообщения, связанные с состоянием, исключая указанные сообщения.

    Args:
        bot (Bot): Экземпляр бота AIogram.
        state (FSMContext): Контекст состояния пользователя.
        chat_id (int): ID чата, из которого удаляются сообщения.
        exclude_message_id (Optional[int]): ID сообщения, которое не следует удалять (устаревший параметр).
        exclude_message_ids (Optional[List[int]]): Список ID сообщений, которые не следует удалять.
    """
    data = await state.get_data()
    current_state = await state.get_state()
    exclude_ids = set()

    # Формируем множество исключений
    if exclude_message_ids is not None:
        exclude_ids.update(exclude_message_ids)
    if exclude_message_id is not None:
        exclude_ids.add(exclude_message_id)

    # Всегда добавляем date_message_id в исключения, если оно существует
    date_message_id = data.get("date_message_id")
    if date_message_id:
        exclude_ids.add(date_message_id)

    # Удаляем только сообщения финального состояния (confirming_operation), сохраняя сводку и сумму до этого
    for state_key, message_key in KEY_MESSAGE_FIELDS.items():
        message_id = data.get(message_key)
        if message_id and message_id not in exclude_ids and current_state == OperationState.confirming_operation.state:
            try:
                await bot.delete_message(chat_id, message_id)
                log.debug(f"Deleted key message with ID {message_id} for state {state_key}")
            except TelegramBadRequest as e:
                if "message can't be deleted" not in str(e).lower() and "message to delete not found" not in str(e).lower():
                    log.warning(f"Failed to delete message {message_id}: {str(e)}")
            except Exception as e:
                log.warning(f"Unexpected error deleting message {message_id}: {str(e)}")

    # Удаляем сводку только на финальном этапе
    summary_message_id = data.get(SUMMARY_MESSAGE_KEY)
    if summary_message_id and summary_message_id not in exclude_ids and current_state == OperationState.confirming_operation.state:
        try:
            await bot.delete_message(chat_id, summary_message_id)
            log.debug(f"Deleted summary message with ID {summary_message_id}")
        except TelegramBadRequest as e:
            if "message can't be deleted" not in str(e).lower() and "message to delete not found" not in str(e).lower():
                log.warning(f"Failed to delete summary message {summary_message_id}: {str(e)}")
        except Exception as e:
            log.warning(f"Unexpected error deleting summary message {summary_message_id}: {str(e)}")


async def delete_tracked_messages(bot: Bot, state: FSMContext, chat_id: int, exclude_message_id: int = None) -> None:
    """Удаляет временные сообщения из списка messages_to_delete."""
    data = await state.get_data()
    messages_to_delete = data.get(TRACKING_KEY, [])
    for message_id in messages_to_delete[:]:  # Копируем список для безопасного удаления
        if exclude_message_id and message_id == exclude_message_id:
            continue  # Пропускаем сообщение, которое нужно сохранить
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass
    if exclude_message_id:
        messages_to_delete = [mid for mid in messages_to_delete if mid != exclude_message_id]
    else:
        messages_to_delete = []
    await state.update_data({TRACKING_KEY: messages_to_delete})


def track_messages(func: Callable) -> Callable:
    """Декоратор для отслеживания и управления сообщениями."""

    @wraps(func)
    async def wrapper(event: Message | CallbackQuery, state: FSMContext, bot: Bot, *args, **kwargs):
        current_state = await state.get_state()
        chat_id = event.chat.id if isinstance(event, Message) else event.message.chat.id
        if isinstance(event, Message):
            if current_state in KEY_MESSAGE_FIELDS:
                await state.update_data({KEY_MESSAGE_FIELDS[current_state]: event.message_id})
            messages_to_delete = (await state.get_data()).get(TRACKING_KEY, [])
            messages_to_delete.append(event.message_id)
            await state.update_data({TRACKING_KEY: messages_to_delete})
        result = await func(event, state, bot, *args, **kwargs)
        await delete_tracked_messages(bot, state, chat_id)
        return result

    return wrapper