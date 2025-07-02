# -*- coding: utf-8 -*-
# FinFlow/src/db/founders.py
"""
Справочник `Founder` и CRUD‑методы для управления данными об учредителях.

Содержит:
    • ORM‑модель `Founder` с полями `founder_id` и `name`.
    • Обратные связи с моделями `Income` и `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей учредителей с логированием и валидацией.

Учредители участвуют в операциях прихода и расхода (статьи 29, 30).
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy import Integer, String, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.logger import configure_logger
from src.db.service.base import Base

logger = configure_logger(prefix="FOUNDERS", color="cyan", level="INFO")


# --------------------------------------------------------------------------- #
# Founder Model                                                               #
# --------------------------------------------------------------------------- #
class Founder(Base):
    """ORM‑модель учредителя."""

    __tablename__ = "founders"

    founder_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Наименование учредителя"
    )

    incomes = relationship("Income", back_populates="founder", lazy="selectin")
    outcomes = relationship("Outcome", back_populates="founder", lazy="selectin")


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_founder(session: AsyncSession, name: str) -> Founder:
    """
    Создать нового учредителя.

    Args:
        session: Асинхронная сессия БД.
        name: Наименование учредителя.

    Returns:
        Созданный объект Founder.

    Raises:
        ValueError: Если name пустое, длиннее 255 символов или содержит недопустимые символы.
        IntegrityError: Если учредитель с таким именем уже существует.
    """
    if not name or len(name) > 255 or not re.match(r'^[\w\s-]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-' or '_'"
        )

    founder = Founder(name=name)
    session.add(founder)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Founder id={founder.founder_id} name={name}")
        return founder
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Founder name='{name}': {exc}")
        raise


async def get_founder(
        session: AsyncSession, founder_id: int
) -> Optional[Founder]:
    """
    Получить учредителя по ID.

    Args:
        session: Асинхронная сессия БД.
        founder_id: Идентификатор учредителя.

    Returns:
        Объект Founder или None.
    """
    stmt = select(Founder).where(Founder.founder_id == founder_id)
    res = await session.execute(stmt)
    founder = res.scalar_one_or_none()
    logger.debug(f"Fetched Founder id={founder_id}: found={founder is not None}")
    return founder


async def get_founders(session: AsyncSession) -> List[Founder]:
    """
    Получить всех учредителей.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Founder.
    """
    stmt = select(Founder)
    res = await session.execute(stmt)
    founders = res.scalars().all()
    logger.debug(f"Fetched {len(founders)} founders")
    return founders


async def update_founder(
        session: AsyncSession, founder_id: int, data: dict
) -> Optional[Founder]:
    """
    Обновить данные учредителя.

    Args:
        session: Асинхронная сессия БД.
        founder_id: Идентификатор изменяемого учредителя.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Founder или None.

    Raises:
        ValueError: При неверном формате 'name' или дубликате имени.
    """
    if "name" in data:
        new_name = data["name"]
        if not new_name or len(new_name) > 255 or not re.match(r'^[\w\s-]+$', new_name):
            raise ValueError(
                "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-' or '_'"
            )
        dup = await session.execute(
            select(Founder).where(
                Founder.name == new_name,
                Founder.founder_id != founder_id
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Founder with name='{new_name}' already exists")

    stmt = (
        update(Founder)
        .where(Founder.founder_id == founder_id)
        .values(**data)
        .returning(Founder)
    )
    res = await session.execute(stmt)
    founder = res.scalar_one_or_none()
    if founder:
        await session.commit()
        logger.info(f"Updated Founder id={founder_id}")
    else:
        await session.rollback()
        logger.warning(f"Founder id={founder_id} not found for update")
    return founder


async def delete_founder(session: AsyncSession, founder_id: int) -> bool:
    """
    Удалить учредителя.

    Args:
        session: Асинхронная сессия БД.
        founder_id: Идентификатор удаляемого учредителя.

    Returns:
        True, если учредитель был удалён; иначе False.
    """
    stmt = delete(Founder).where(Founder.founder_id == founder_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Founder id={founder_id}")
    else:
        await session.rollback()
        logger.warning(f"Founder id={founder_id} not found for delete")
    return deleted
