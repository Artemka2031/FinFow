# -*- coding: utf-8 -*-
# FinFlow/src/db/creditors.py
"""
Справочник `Creditor` и CRUD‑методы для управления данными о кредиторах.

Содержит:
    • ORM‑модель `Creditor` с полями `creditor_id` и `name`.
    • Обратные связи с моделями `Income` и `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей кредиторов с логированием и валидацией.

Кредиторы участвуют в операциях прихода и выбытия средств.
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import select, update, delete

from src.db.service.base import Base
from src.core.logger import configure_logger

logger = configure_logger(prefix="CREDITORS", color="cyan", level="INFO")

# --------------------------------------------------------------------------- #
# Creditor Model                                                              #
# --------------------------------------------------------------------------- #


class Creditor(Base):
    """ORM‑модель кредитора."""

    __tablename__ = "creditors"

    creditor_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Наименование кредитора"
    )

    incomes = relationship(
        "Income", back_populates="creditor", lazy="selectin"
    )
    outcomes = relationship(
        "Outcome", back_populates="creditor", lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_creditor(session: AsyncSession, name: str) -> Creditor:
    """
    Создать нового кредитора.

    Args:
        session: Асинхронная сессия БД.
        name: Наименование кредитора.

    Returns:
        Созданный объект Creditor.

    Raises:
        ValueError: Если name пустой, длиннее 255 символов или содержит недопустимые символы.
        IntegrityError: Если кредитор с таким именем уже существует.
    """
    if not name or len(name) > 255 or not re.match(r'^[\w\s\-\.,\u0400-\u04FF]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 chars, allowed: letters (Latin/Cyrillic), digits, spaces, '-', '_', '.', ','"
        )

    creditor = Creditor(name=name)
    session.add(creditor)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Creditor id={creditor.creditor_id} name={name}")
        return creditor
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Creditor name='{name}': {exc}")
        raise


async def get_creditor(
    session: AsyncSession, creditor_id: int
) -> Optional[Creditor]:
    """
    Получить кредитора по ID.

    Args:
        session: Асинхронная сессия БД.
        creditor_id: Идентификатор кредитора.

    Returns:
        Объект Creditor или None.
    """
    stmt = select(Creditor).where(Creditor.creditor_id == creditor_id)
    res = await session.execute(stmt)
    creditor = res.scalar_one_or_none()
    logger.debug(f"Fetched Creditor id={creditor_id}: found={creditor is not None}")
    return creditor


async def get_creditors(session: AsyncSession) -> List[Creditor]:
    """
    Получить список всех кредиторов.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Creditor.
    """
    stmt = select(Creditor)
    res = await session.execute(stmt)
    creditors = res.scalars().all()
    logger.debug(f"Fetched {len(creditors)} creditors")
    return creditors


async def update_creditor(
    session: AsyncSession, creditor_id: int, data: dict
) -> Optional[Creditor]:
    """
    Обновить данные кредитора.

    Args:
        session: Асинхронная сессия БД.
        creditor_id: ID изменяемого кредитора.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Creditor или None.

    Raises:
        ValueError: При неверном формате name или дубликате имени.
    """
    if "name" in data:
        new_name = data["name"]
        if not new_name or len(new_name) > 255 or not re.match(r'^[\w\s\-\.,]+$', new_name):
            raise ValueError(
                "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-', '_', '.', ','"
            )
        # Проверка дублей
        dup = await session.execute(
            select(Creditor).where(
                Creditor.name == new_name,
                Creditor.creditor_id != creditor_id
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Creditor with name='{new_name}' already exists")

    stmt = (
        update(Creditor)
        .where(Creditor.creditor_id == creditor_id)
        .values(**data)
        .returning(Creditor)
    )
    res = await session.execute(stmt)
    creditor = res.scalar_one_or_none()
    if creditor:
        await session.commit()
        logger.info(f"Updated Creditor id={creditor_id}")
    else:
        await session.rollback()
        logger.warning(f"Creditor id={creditor_id} not found for update")
    return creditor


async def delete_creditor(session: AsyncSession, creditor_id: int) -> bool:
    """
    Удалить кредитора.

    Args:
        session: Асинхронная сессия БД.
        creditor_id: Идентификатор удаляемого кредитора.

    Returns:
        True, если кредитор был удалён; иначе False.
    """
    stmt = delete(Creditor).where(Creditor.creditor_id == creditor_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Creditor id={creditor_id}")
    else:
        await session.rollback()
        logger.warning(f"Creditor id={creditor_id} not found for delete")
    return deleted
