# -*- coding: utf-8 -*-
# FinFlow/src/bot/state/operation_state.py
import json
from datetime import timedelta

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from src.core.config import get_settings

# ───────────────────── Инициализация RedisStorage ────────────────────────
settings = get_settings()
redis = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    db=0,
    decode_responses=True,
)
storage = RedisStorage(
    redis=redis,
    state_ttl=timedelta(days=7),
    data_ttl=timedelta(days=7),
    json_loads=json.loads,
    json_dumps=json.dumps,
)

# ─────────────────────────── States Group ────────────────────────────────
class OperationState(StatesGroup):
    # Шаг 1: даты
    choosing_recording_date = State()
    choosing_operation_date = State()

    # Шаг 2: тип операции
    choosing_operation_type = State()

    # ── Приход
    choosing_income_wallet   = State()  # Шаг 3
    choosing_income_article  = State()  # Шаг 4
    choosing_income_project  = State()  # Шаг 5 (ст.1)
    choosing_income_creditor = State()  # Шаг 5 (ст.27,32)
    choosing_income_founder  = State()  # Шаг 5 (ст.28)
    choosing_income_additional_info = State()  # Шаг 5 (прочие)

    # ── Перемещение
    choosing_from_wallet = State()  # Шаг 3
    choosing_to_wallet   = State()  # Шаг 4

    # ── Выбытие
    choosing_outcome_wallet_or_creditor = State()  # Шаг 3
    choosing_outcome_wallet       = State()
    choosing_outcome_creditor     = State()
    choosing_outcome_chapter      = State()  # Шаг 4
    choosing_outcome_project      = State()  # Шаг 5 («По проектам»)
    choosing_outcome_general_type = State()  # Шаг 5 («Общие»)
    choosing_outcome_article      = State()  # Шаг 6
    choosing_contractor           = State()  # Шаг 7 (ст.3)
    choosing_material             = State()  # Шаг 7 (ст.4)
    choosing_employee             = State()  # Шаг 7 (ст.7,8,11)
    choosing_creditor             = State()  # Шаг 7 (ст.29)
    choosing_founder              = State()  # Шаг 7 (ст.30)
    entering_outcome_details      = State()  # зарезервировано

    # Шаг 8: сумма
    entering_operation_amount = State()

    # Шаг 9: коэффициент экономии (0…1)  ← NEW
    entering_saving_coeff = State()

    # Шаг 10: комментарий
    entering_operation_comment = State()

    # Шаг 11: подтверждение
    confirming_operation = State()

# ─────────────────────────── reset_state ─────────────────────────────────
async def reset_state(state: FSMContext, clear_history: bool = True) -> None:
    """Полный сброс FSM ‑данных пользователя."""
    current_data = await state.get_data()
    preserved_keys = {"messages_to_delete"}
    if not clear_history:
        preserved_keys.add("state_history")

    reset_data = {k: None for k in current_data if k not in preserved_keys}
    update_data = {
        "state_history": [] if clear_history else current_data.get("state_history", []),
        "contractor_name": None,
        "material_name": None,
        "employee_name": None,
        "outcome_article_creditor": None,
        "outcome_founder": None,
        "saving_coeff": None,       # сбрасываем новый коэффициент
    }
    update_data.update(reset_data)
    await state.update_data(**update_data)
    await state.set_state(None)
