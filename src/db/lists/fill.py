# -*- coding: utf-8 -*-
# FinFlow/src/db/lists/fill.py
"""
Скрипт заполнения справочников начальными данными.

Использует:
    • create_wallet, create_creditor, create_article, create_project,
      create_employee, create_material, create_founder, create_contractor
    • get_async_session для получения сессии.
"""

import asyncio

from src.core.logger import configure_logger
from src.db.models.articles import create_article
from src.db.models.contractors import create_contractor
from src.db.models.creditors import create_creditor
from src.db.models.employees import create_employee
from src.db.models.founders import create_founder
from src.db.models.materials import create_material
from src.db.models.projects import create_project
from src.db.models.wallets import create_wallet
from src.db.service.session import get_async_session

logger = configure_logger(prefix="FILL", color="green", level="INFO")

# 1. Wallets
WALLETS = [
    ("w1", "РС ТОЧКА"),
    ("w2", "РС ТОЧКА (второй счет)"),
    ("w3", "РС ОЗОН банк"),
    ("w4", "РС УРАЛСИБ"),
    ("w5", "РС АкБарс"),
    ("w6", "КРЕДИТОРЫ РАСЧЕТНЫЙ"),
    ("w7", "РС ВТБ Банк"),
    ("w8", "КАССА"),
    ("w9", "ФОНДЫ"),
]

# 2. Creditors
CREDITORS = [
    ("ООО ШАФТСТИЛ",),
    ("ООО СПС",),
    ("ООО БС СПб",),
    ("Горчаков",),
    ("ООО Строитель",),
    ("ЗАО ИнвестСтрой",),
    ("ООО ЛенДорСтрой",),
    ("ИП Иванов",),
    ("ООО Северный Ветер",),
    ("ЗАО РемонтПро",),
    ("ООО СтальПрофиль",),
    ("ИП Петров",),
]

# 3. Articles: (article_id ignored by create, code & name used)
ARTICLES = [
    (1, 1, "Выручка", "Выручка (по проектам)"),
    (2, 2, "Прочие доходы", "Прочие доходы"),
    (3, 3, "ФОТ бригад/подряд.", "ПО ПРОЕКТАМ. ФОТ БРИГАДЫ И ПОДРЯДЧИКИ"),
    (4, 4, "Материалы проектов", "ПО ПРОЕКТАМ. МАТЕРИАЛЫ"),
    (5, 5, "Доставка/подъем", "ПО ПРОЕКТАМ. ДОСТАВКА И ПОДЪЕМ"),
    (6, 6, "Уборка/мусор", "ПО ПРОЕКТАМ. УБОРКА И ВЫВОЗ МУСОРА"),
    (7, 7, "Бонус отдела продаж", "ПО ПРОЕКТАМ. БОНУСЫ ОТДЕЛА ПРОДАЖ"),
    (8, 8, "Бонус строителей", "ПО ПРОЕКТАМ. БОНУСЫ СТРОИТ. ПЕРСОНАЛА"),
    (9, 9, "Представительские", "ПО ПРОЕКТАМ. ПРЕДСТАВИТЕЛЬСКИЕ РАСХОДЫ"),
    (10, 10, "Прочие прямые", "ПО ПРОЕКТАМ. ПРОЧИЕ ПРЯМЫЕ"),
    (11, 11, "ФОТ штатных", "ФОТ штатного производств. персонала"),
    (12, 12, "Техника/инвентарь", "Расходы на технику и инвентаря"),
    (13, 13, "Расходы на ОС", "Расходы на ОС"),
    (14, 14, "ФОТ админ.", "ФОТ административного персонала"),
    (15, 15, "ФОТ коммерц.", "ФОТ коммерческого персонала"),
    (16, 16, "Налоги ФОТ", "Налоги ФОТ"),
    (17, 17, "Аренда офис/склад", "Аренда и содержание (офис, склад)"),
    (18, 18, "Админ. подрядчики", "Административные подрядчики"),
    (19, 19, "Корп. расходы", "Корпоративные: подарки, персонал, обучение"),
    (20, 20, "Маркетинг", "Маркетинг"),
    (21, 21, "Онлайн сервисы", "Онлайн сервисы"),
    (22, 22, "Возвраты подрядч.", "ВОЗВРАТЫ от подрядчиков"),
    (23, 23, "Банк/РКО/комиссии", "Банки/РКО/комиссии"),
    (24, 24, "Прочие расходы", "Прочие расходы"),
    (25, 25, "Налоги БАЗА", "Налоги БАЗА"),
    (26, 26, "Проценты по займам", "% по займам и кредитам"),
    (27, 27, "Получение кредитов", "Получение кредитов и займов"),
    (28, 28, "Вклады собственн.", "Вклады от собственников"),
    (29, 29, "Оплаты по кредитам", "Оплаты по кредитам и займам"),
    (30, 30, "Дивиденды", "Дивиденды"),
    (31, 31, "Инвест. поступл.", "Прочие поступл. от инвест. операций"),
    (32, 32, "Возврат кредитов", "Возврат кредитов и займов (нам вернули)"),
    (33, 33, "Продажа ОС", "Продажа ОС"),
    (34, 34, "Покупка/ремонт ОС", "Покупка ОС и ремонт ОС"),
    (35, 35, "Выдача кредитов", "Выдача кредитов и займов (мы выдали)"),
]

# 4. Projects
PROJECTS = [
    (1, "Коттедж Крокусы"),
    (2, "Острава Ветеранов"),
    (3, "Кв. Наука"),
    (4, "Коттедж Крокусы 2"),
    (5, "Сев. Минвата"),
    (6, "Елиз. Парапет"),
    (7, "Пулково 42к6"),
    (8, "Пулково 36"),
    (9, "Монодом"),
    (10, "Лаврики 57"),
    (11, "Русан. Шов"),
    (12, "Мойка Аполло"),
    (13, "ИМОП"),
    (14, "Лаврики 55"),
    (15, "Куш. Дорога"),
    (16, "Общежитие"),
]

# 5. Employees
EMPLOYEES = [
    (1, "Ваня - Мастер"),
    (2, "Ваня - Помощник"),
    (3, "Ваня - Инженер"),
    (4, "Ваня - Стажер"),
    (5, "Саша - Менеджер"),
    (6, "Саша - Бригадир"),
    (7, "Саша - Оператор"),
    (8, "Саша - Снабженец"),
    (9, "Петр - Рабочий"),
    (10, "Петр - Инженер"),
    (11, "Игорь - Мастер"),
    (12, "Игорь - Снабженец"),
]

# 6. Materials
MATERIALS = [
    (1, "Цемент М500"),
    (2, "Песок строительный"),
    (3, "Щебень фракц. 20-40"),
    (4, "Арматура 12 мм"),
    (5, "Кирпич красный"),
    (6, "Штукатурка гипсовая"),
    (7, "Кровельный профиль"),
    (8, "Гипсокартон 12 мм"),
    (9, "Лак для дерева"),
    (10, "Краска фасадная"),
    (11, "Плитка керамогранит"),
    (12, "Трубы ПВХ 50 мм"),
    (13, "Электрокабель 2.5 кв"),
    (14, "Дюбели 6x40"),
    (15, "Саморезы 4.2x50"),
]

# 7. Founders
FOUNDERS = [(1, "Андрей"), (2, "Степан")]

# 8. Contractors
CONTRACTORS = [
    (1, "Бригада 1"),
    (2, "Бригада 2"),
    (3, "Бригада 3"),
    (4, "Бригада 4"),
    (5, "Бригада 5"),
    (6, "Бригада 6"),
    (7, "Бригада 7"),
    (8, "Бригада 8"),
    (9, "Бригада 9"),
    (10, "Бригада 10"),
    (11, "Бригада 11"),
    (12, "Бригада 12"),
    (13, "Подрядчик 1"),
    (14, "Подрядчик 2"),
    (15, "Подрядчик 3"),
    (16, "Подрядчик 4"),
    (17, "Подрядчик 5"),
    (18, "Подрядчик 6"),
    (19, "Подрядчик 7"),
    (20, "Подрядчик 8"),
    (21, "Подрядчик 9"),
    (22, "Подрядчик 10"),
]


async def fill_all():
    async with get_async_session() as session:
        # Wallets
        for wid, number in WALLETS:
            try:
                await create_wallet(session, wid, number)
            except Exception as e:
                logger.warning(f"FILL Wallet '{wid}' skipped: {e}")

        # Creditors
        for name, in CREDITORS:
            try:
                await create_creditor(session, name)
            except Exception as e:
                logger.warning(f"FILL Creditor '{name}' skipped: {e}")

        # Articles
        for _, code, short_name, name in ARTICLES:
            try:
                await create_article(session, code, short_name, name)
            except Exception as e:
                logger.warning(f"FILL Article code={code} skipped: {e}")

        # Projects
        for _, name in PROJECTS:
            try:
                await create_project(session, name)
            except Exception as e:
                logger.warning(f"FILL Project '{name}' skipped: {e}")

        # Employees
        for _, name in EMPLOYEES:
            try:
                await create_employee(session, name)
            except Exception as e:
                logger.warning(f"FILL Employee '{name}' skipped: {e}")

        # Materials
        for _, name in MATERIALS:
            try:
                await create_material(session, name)
            except Exception as e:
                logger.warning(f"FILL Material '{name}' skipped: {e}")

        # Founders
        for _, name in FOUNDERS:
            try:
                await create_founder(session, name)
            except Exception as e:
                logger.warning(f"FILL Founder '{name}' skipped: {e}")

        # Contractors
        for _, name in CONTRACTORS:
            try:
                await create_contractor(session, name)
            except Exception as e:
                logger.warning(f"FILL Contractor '{name}' skipped: {e}")

        logger.info("FILL Database fill completed.")


if __name__ == "__main__":
    asyncio.run(fill_all())
