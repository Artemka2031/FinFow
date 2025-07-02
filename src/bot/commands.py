# -*- coding: utf-8 -*-
# FinFlow/src/bot/commands.py
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

async def set_bot_commands(bot: Bot):
    """
    Регистрирует команды бота в меню Telegram.
    """
    commands = [
        BotCommand(command="/start", description="Запустить бота"),
        BotCommand(command="/start_operation", description="Начать ввод операции"),
        BotCommand(command="/cancel_operation", description="Отменить текущую операцию"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())