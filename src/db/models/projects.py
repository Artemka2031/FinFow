# -*- coding: utf-8 -*-
# FinFlow/src/db/models/projects.py
"""
Справочник `Project` и CRUD‑методы для управления проектами, связанными с операциями прихода и расхода.

Содержит:
    • ORM‑модель `Project` с полями `project_id` и `name`.
    • Обратные связи с моделями `Income` и `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей проектов с логированием и валидацией.

Каждый проект имеет уникальный идентификатор и имя (непустое, до 255 символов).
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

logger = configure_logger(prefix="PROJECTS", color="magenta", level="INFO")

# --------------------------------------------------------------------------- #
# Project Model                                                               #
# --------------------------------------------------------------------------- #


class Project(Base):
    """ORM‑модель проекта, к которому привязываются приходы и расходы."""

    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Наименование проекта (непустое, макс. 255 символов)"
    )

    incomes = relationship(
        "Income", back_populates="project", lazy="selectin"
    )
    outcomes = relationship(
        "Outcome", back_populates="project", lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_project(session: AsyncSession, name: str) -> Project:
    """
    Создать новый проект.

    Args:
        session: Асинхронная сессия БД.
        name: Наименование проекта.

    Returns:
        Созданный объект Project.

    Raises:
        ValueError: Если name пустое или длиннее 255 символов,
                    либо содержит недопустимые символы.
        IntegrityError: Если проект с таким именем уже существует.
    """
    # Валидация имени: не пустое, <=255, допускаем буквы (латинские/кириллические), цифры, пробел, дефис, подчёркивание
    if not name or len(name) > 255 or not re.match(r'^[\w\s\-\_\u0400-\u04FF]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 characters, and contain only letters (Latin/Cyrillic), digits, spaces, '-' or '_'"
        )

    project = Project(name=name)
    session.add(project)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Project id={project.project_id} name={name}")
        return project
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Project name='{name}': {exc}")
        raise


async def get_project(
    session: AsyncSession, project_id: int
) -> Optional[Project]:
    """
    Получить проект по ID.

    Args:
        session: Асинхронная сессия БД.
        project_id: Идентификатор проекта.

    Returns:
        Объект Project или None.
    """
    stmt = select(Project).where(Project.project_id == project_id)
    res = await session.execute(stmt)
    project = res.scalar_one_or_none()
    logger.debug(f"Fetched Project id={project_id}: found={project is not None}")
    return project


async def get_projects(session: AsyncSession) -> List[Project]:
    """
    Получить все проекты.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Project.
    """
    stmt = select(Project)
    res = await session.execute(stmt)
    projects = res.scalars().all()
    logger.debug(f"Fetched {len(projects)} projects")
    return projects


async def update_project(
    session: AsyncSession, project_id: int, data: dict
) -> Optional[Project]:
    """
    Обновить данные проекта.

    Args:
        session: Асинхронная сессия БД.
        project_id: Идентификатор изменяемого проекта.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Project или None.

    Raises:
        ValueError: При неверном формате 'name' или дубликате имени.
    """
    if "name" in data:
        new_name = data["name"]
        if not new_name or len(new_name) > 255 or not re.match(r'^[\w\s-]+$', new_name):
            raise ValueError(
                "name must be non-empty, ≤255 characters, and contain only letters, digits, spaces, '-' or '_'"
            )

    stmt = (
        update(Project)
        .where(Project.project_id == project_id)
        .values(**data)
        .returning(Project)
    )
    res = await session.execute(stmt)
    project = res.scalar_one_or_none()
    if project:
        await session.commit()
        logger.info(f"Updated Project id={project_id}")
    else:
        await session.rollback()
        logger.warning(f"Project id={project_id} not found for update")
    return project


async def delete_project(session: AsyncSession, project_id: int) -> bool:
    """
    Удалить проект.

    Args:
        session: Асинхронная сессия БД.
        project_id: Идентификатор удаляемого проекта.

    Returns:
        True, если проект удалён; иначе False.
    """
    stmt = delete(Project).where(Project.project_id == project_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Project id={project_id}")
    else:
        await session.rollback()
        logger.warning(f"Project id={project_id} not found for delete")
    return deleted