# -*- coding: utf-8 -*-
# FinFlow/src/bot/keyboards/__init__.py
from aiogram.filters.callback_data import CallbackData

class NavCallback(CallbackData, prefix="nav"):
    """CallbackData для навигации (например, кнопка «Назад»)."""
    action: str

from .article_kb import create_article_keyboard
from .contractor_kb import create_contractor_keyboard
from .creditor_kb import create_creditor_keyboard
from .employee_kb import create_employee_keyboard
from .founder_kb import create_founder_keyboard
from .material_kb import create_material_keyboard
from .project_kb import create_project_keyboard
from .wallet_kb import create_wallet_keyboard