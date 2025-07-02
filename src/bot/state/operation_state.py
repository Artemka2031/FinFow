# -*- coding: utf-8 -*-
# FinFlow/src/bot/state/operation_state.py
import json
from datetime import timedelta

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from src.core.config import get_settings

# Инициализация RedisStorage
settings = get_settings()
redis = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    db=0,
    decode_responses=True
)
storage = RedisStorage(
    redis=redis,
    state_ttl=timedelta(days=7),  # TTL для состояний - 7 дней
    data_ttl=timedelta(days=7),  # TTL для данных - 7 дней
    json_loads=json.loads,
    json_dumps=json.dumps
)


class OperationState(StatesGroup):
    # Шаг 1: Выбор даты операции
    choosing_recording_date = State()
    choosing_operation_date = State()

    # Шаг 2: Выбор типа операции
    choosing_operation_type = State()

    # Бизнес-логика для Приходов
    choosing_income_wallet = State()  # Шаг 3
    choosing_income_article = State()  # Шаг 4
    choosing_income_project = State()  # Шаг 5 (для статьи 1)
    choosing_income_creditor = State()  # Шаг 5 (для статей 27, 32)
    choosing_income_founder = State()  # Шаг 5 (для статьи 28)
    choosing_income_additional_info = State()  # Шаг 5 (для остальных случаев)

    # Бизнес-логика для Переводов
    choosing_from_wallet = State()  # Шаг 3
    choosing_to_wallet = State()  # Шаг 4

    # Бизнес-логика для Выбытий
    choosing_outcome_wallet_or_creditor = State()  # Шаг 3
    choosing_outcome_wallet = State()
    choosing_outcome_creditor = State()
    choosing_outcome_chapter = State()  # Шаг 4
    choosing_outcome_project = State()  # Шаг 5 (для "По проекту")
    choosing_outcome_general_type = State()  # Шаг 5 (для "Общие")
    choosing_outcome_article = State()  # Шаг 6
    choosing_contractor = State()      # Шаг 7 (для статьи 3)
    choosing_material = State()        # Шаг 7 (для статьи 4)
    choosing_employee = State()        # Шаг 7 (для статей 7, 8, 11)
    choosing_creditor = State()        # Шаг 7 (для статьи 29)
    choosing_founder = State()         # Шаг 7 (для статьи 30)
    entering_outcome_details = State() # Шаг 7 (для деталей, например, сотрудник, материал)

    # Шаг 8: Ввод суммы операции
    entering_operation_amount = State()

    # Шаг 9: Ввод комментария операции и подтверждение
    entering_operation_comment = State()
    confirming_operation = State()     # Шаг 10


async def reset_state(state: FSMContext, clear_history: bool = True) -> None:
    """Полный сброс состояния и данных."""
    current_data = await state.get_data()
    preserved_keys = {"messages_to_delete"}
    if not clear_history:
        preserved_keys.add("state_history")

    reset_data = {k: None for k in current_data if k not in preserved_keys}
    update_data = {"state_history": [] if clear_history else current_data.get("state_history", [])}
    update_data.update(reset_data)
    # Добавляем новые ключи для сброса
    update_data.update({
        "contractor_name": None,
        "material_name": None,
        "employee_name": None,
        "outcome_article_creditor": None,
        "outcome_founder": None,
    })
    await state.update_data(**update_data)
    await state.set_state(None)