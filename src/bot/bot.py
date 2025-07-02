# -*- coding: utf-8 -*-
# FinFlow/src/bot/bot.py
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.bot.middlewares.state_logger import StateLoggerMiddleware
from src.bot.routers import date_type_router, start_router, amount_comment_router, command_router, navigation_router,\
    transfer_router, confirm_transfer_router
from src.bot.commands import set_bot_commands
from src.bot.routers.income import income_router, confirm_income_router
from src.bot.routers.outcome import outcome_router, outcome_articles, confirm_outcome_router
from src.bot.state.operation_state import storage
from src.core.config import get_settings
from src.core.logger import configure_logger

logger = configure_logger("[BOT]", "green", level="DEBUG")

settings = get_settings()

async def main():
    logger.info("Starting FinFlow bot application")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=storage)

    # Регистрация команд
    await set_bot_commands(bot)

    dp.message.middleware(StateLoggerMiddleware())
    dp.callback_query.middleware(StateLoggerMiddleware())

    dp.include_routers(
        start_router,
        command_router,
        navigation_router,

        date_type_router,
        amount_comment_router,

        income_router,
        confirm_income_router,

        transfer_router,
        confirm_transfer_router,

        outcome_router,
        outcome_articles,
        confirm_outcome_router
    )

    try:
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot)
    finally:
        logger.info("Bot is shutting down...")
        await bot.session.close()
        await storage.close()

def create_bot():
    """Создаёт и возвращает экземпляр бота для тестирования."""
    return main()

if __name__ == "__main__":
    asyncio.run(main())