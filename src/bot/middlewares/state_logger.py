from typing import Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject

from src.core.logger import configure_logger


class StateLoggerMiddleware(BaseMiddleware):
    def __init__(self):
        self.logger = configure_logger(prefix="STATE_LOG", color="green", level="INFO")

    async def __call__(
        self,
        handler: Callable,            # следующий слой
        event: TelegramObject,        # апдейт
        data: dict                    # словарь зависимостей
    ):
        state: FSMContext | None = data.get("state")   # <‑ правильный способ
        user_id = getattr(event.from_user, "id", "unknown")

        if state is None:
            self.logger.warning(f"User {user_id}: no FSMContext, skipping logging.")
            return await handler(event, data)

        # читаем текущее состояние и данные
        current_state = await state.get_state()
        state_name = current_state.split(":")[-1] if current_state else "None"

        payload = await state.get_data()
        payload_str = ", ".join(f"{k}={v}" for k, v in payload.items() if v is not None)

        # self.logger.info(
        #     f"User {user_id}: Current state = {state_name}, Data = {{{payload_str}}}"
        # )

        return await handler(event, data)              # не забываем пропускать дальше
