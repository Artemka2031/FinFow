# -*- coding: utf-8 -*-
# FinFlow/src/db/materials.py
"""
Справочник `Material` и CRUD‑методы для управления данными о материалах.

Содержит:
    • ORM‑модель `Material` с полями `material_id` и `name`.
    • Обратную связь с моделью `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей материалов с логированием и валидацией.

Материалы используются в операциях выбытия (пример: статьи 3, 4).
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

logger = configure_logger(prefix="MATERIALS", color="magenta", level="INFO")


# --------------------------------------------------------------------------- #
# Material Model                                                              #
# --------------------------------------------------------------------------- #
class Material(Base):
    """ORM‑модель материала."""

    __tablename__ = "materials"

    material_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Наименование материала"
    )

    outcomes = relationship(
        "Outcome", back_populates="material", lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_material(session: AsyncSession, name: str) -> Material:
    """
    Создать новый материал.

    Args:
        session: Асинхронная сессия БД.
        name: Наименование материала.

    Returns:
        Созданный объект Material.

    Raises:
        ValueError: Если name пустое, длиннее 255 символов или содержит недопустимые символы.
        IntegrityError: Если материал с таким именем уже существует.
    """
    # Валидация: непустое, ≤255, допускаем буквы, цифры, пробел, дефис или подчёркивание
    if not name or len(name) > 255 or not re.match(r'^[\w\s-]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-' or '_'"
        )

    material = Material(name=name)
    session.add(material)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Material id={material.material_id} name={name}")
        return material
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Material name='{name}': {exc}")
        raise


async def get_material(
        session: AsyncSession, material_id: int
) -> Optional[Material]:
    """
    Получить материал по ID.

    Args:
        session: Асинхронная сессия БД.
        material_id: Идентификатор материала.

    Returns:
        Объект Material или None.
    """
    stmt = select(Material).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    logger.debug(f"Fetched Material id={material_id}: found={material is not None}")
    return material


async def get_materials(session: AsyncSession) -> List[Material]:
    """
    Получить все материалы.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Material.
    """
    stmt = select(Material)
    res = await session.execute(stmt)
    materials = res.scalars().all()
    logger.debug(f"Fetched {len(materials)} materials")
    return materials


async def update_material(
        session: AsyncSession, material_id: int, data: dict
) -> Optional[Material]:
    """
    Обновить материал.

    Args:
        session: Асинхронная сессия БД.
        material_id: Идентификатор изменяемого материала.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Material или None.

    Raises:
        ValueError: При неверном формате 'name' или дубликате.
    """
    if "name" in data:
        new_name = data["name"]
        if not new_name or len(new_name) > 255 or not re.match(r'^[\w\s-]+$', new_name):
            raise ValueError(
                "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-' or '_'"
            )
        # Проверка дубликата
        dup = await session.execute(
            select(Material).where(
                Material.name == new_name,
                Material.material_id != material_id
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Material with name='{new_name}' already exists")

    stmt = (
        update(Material)
        .where(Material.material_id == material_id)
        .values(**data)
        .returning(Material)
    )
    res = await session.execute(stmt)
    material = res.scalar_one_or_none()
    if material:
        await session.commit()
        logger.info(f"Updated Material id={material_id}")
    else:
        await session.rollback()
        logger.warning(f"Material id={material_id} not found for update")
    return material


async def delete_material(session: AsyncSession, material_id: int) -> bool:
    """
    Удалить материал.

    Args:
        session: Асинхронная сессия БД.
        material_id: Идентификатор удаляемого материала.

    Returns:
        True, если материал был удалён; иначе False.
    """
    stmt = delete(Material).where(Material.material_id == material_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Material id={material_id}")
    else:
        await session.rollback()
        logger.warning(f"Material id={material_id} not found for delete")
    return deleted
