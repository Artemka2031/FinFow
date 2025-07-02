# -*- coding: utf-8 -*-
# FinFlow/src/db/contractors.py
"""
Справочник `Contractor` и CRUD‑методы для управления данными о подрядчиках.

Содержит:
    • ORM‑модель `Contractor` с полями `contractor_id` и `name`.
    • Обратную связь с моделью `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей подрядчиков с логированием и валидацией.

Подрядчики используются в операциях выбытия (статьи 3, 4, 7, 8).
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy import Integer, String
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.logger import configure_logger
from src.db.service.base import Base

logger = configure_logger(prefix="CONTRACTORS", color="magenta", level="INFO")


# --------------------------------------------------------------------------- #
# Contractor Model                                                            #
# --------------------------------------------------------------------------- #


class Contractor(Base):
    """ORM‑модель подрядчика (бригады, субподрядчика)."""

    __tablename__ = "contractors"

    contractor_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Наименование подрядчика"
    )

    outcomes = relationship(
        "Outcome", back_populates="contractor", lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_contractor(session: AsyncSession, name: str) -> Contractor:
    """
    Создать нового подрядчика.

    Args:
        session: Асинхронная сессия БД.
        name: Наименование подрядчика.

    Returns:
        Созданный объект Contractor.

    Raises:
        ValueError: Если name пустое, длиннее 255 символов или содержит недопустимые символы.
        IntegrityError: Если подрядчик с таким именем уже существует.
    """
    # Валидация: непустое, ≤255, допускаем буквы, цифры, пробел, дефис, подчёркивание, точку, запятую
    if not name or len(name) > 255 or not re.match(r'^[\w\s\-\.,]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-', '_', '.', ','"
        )

    contractor = Contractor(name=name)
    session.add(contractor)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Contractor id={contractor.contractor_id} name={name}")
        return contractor
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Contractor name='{name}': {exc}")
        raise


async def get_contractor(
        session: AsyncSession, contractor_id: int
) -> Optional[Contractor]:
    """
    Получить подрядчика по ID.

    Args:
        session: Асинхронная сессия БД.
        contractor_id: Идентификатор подрядчика.

    Returns:
        Объект Contractor или None.
    """
    stmt = select(Contractor).where(Contractor.contractor_id == contractor_id)
    res = await session.execute(stmt)
    contractor = res.scalar_one_or_none()
    logger.debug(
        f"Fetched Contractor id={contractor_id}: found={contractor is not None}"
    )
    return contractor


async def get_contractors(session: AsyncSession) -> List[Contractor]:
    """
    Получить список всех подрядчиков.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Contractor.
    """
    stmt = select(Contractor)
    res = await session.execute(stmt)
    contractors = res.scalars().all()
    logger.debug(f"Fetched {len(contractors)} contractors")
    return contractors


async def update_contractor(
        session: AsyncSession, contractor_id: int, data: dict
) -> Optional[Contractor]:
    """
    Обновить данные подрядчика.

    Args:
        session: Асинхронная сессия БД.
        contractor_id: Идентификатор изменяемого подрядчика.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Contractor или None.

    Raises:
        ValueError: При неверном формате 'name' или дубликате.
    """
    if "name" in data:
        new_name = data["name"]
        if not new_name or len(new_name) > 255 or not re.match(r'^[\w\s\-\.,]+$', new_name):
            raise ValueError(
                "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-', '_', '.', ','"
            )
        # Проверка дубликата
        dup = await session.execute(
            select(Contractor).where(
                Contractor.name == new_name,
                Contractor.contractor_id != contractor_id
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Contractor with name='{new_name}' already exists")

    stmt = (
        update(Contractor)
        .where(Contractor.contractor_id == contractor_id)
        .values(**data)
        .returning(Contractor)
    )
    res = await session.execute(stmt)
    contractor = res.scalar_one_or_none()
    if contractor:
        await session.commit()
        logger.info(f"Updated Contractor id={contractor_id}")
    else:
        await session.rollback()
        logger.warning(f"Contractor id={contractor_id} not found for update")
    return contractor


async def delete_contractor(session: AsyncSession, contractor_id: int) -> bool:
    """
    Удалить подрядчика.

    Args:
        session: Асинхронная сессия БД.
        contractor_id: Идентификатор удаляемого подрядчика.

    Returns:
        True, если подрядчик был удалён; иначе False.
    """
    stmt = delete(Contractor).where(Contractor.contractor_id == contractor_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Contractor id={contractor_id}")
    else:
        await session.rollback()
        logger.warning(f"Contractor id={contractor_id} not found for delete")
    return deleted
