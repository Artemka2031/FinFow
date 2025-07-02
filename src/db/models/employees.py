# -*- coding: utf-8 -*-
# FinFlow/src/db/employees.py
"""
Справочник `Employee` и CRUD‑методы для управления данными о сотрудниках.

Содержит:
    • ORM‑модель `Employee` с полями `employee_id` и `name`.
    • Обратную связь с моделью `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей сотрудников с логированием и валидацией.

Сотрудники участвуют в операциях выбытия (статьи 3, 4, 7, 8, 11).
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

logger = configure_logger(prefix="EMPLOYEES", color="yellow", level="INFO")


# --------------------------------------------------------------------------- #
# Employee Model                                                              #
# --------------------------------------------------------------------------- #


class Employee(Base):
    """ORM‑модель сотрудника."""

    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Имя сотрудника"
    )

    outcomes = relationship(
        "Outcome", back_populates="employee", lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_employee(session: AsyncSession, name: str) -> Employee:
    """
    Создать нового сотрудника.

    Args:
        session: Асинхронная сессия БД.
        name: Имя сотрудника.

    Returns:
        Созданный объект Employee.

    Raises:
        ValueError: Если name пустое, длиннее 255 символов или содержит недопустимые символы.
        IntegrityError: Если сотрудник с таким именем уже существует.
    """
    # Валидация: непустое, ≤255, буквы, цифры, пробел, дефис или подчёркивание
    if not name or len(name) > 255 or not re.match(r'^[\w\s-]+$', name):
        raise ValueError(
            "name must be non-empty, ≤255 chars, allowed: letters, digits, spaces, '-' or '_'"
        )

    employee = Employee(name=name)
    session.add(employee)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Employee id={employee.employee_id} name={name}")
        return employee
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Employee name='{name}': {exc}")
        raise


async def get_employee(
        session: AsyncSession, employee_id: int
) -> Optional[Employee]:
    """
    Получить сотрудника по ID.

    Args:
        session: Асинхронная сессия БД.
        employee_id: Идентификатор сотрудника.

    Returns:
        Объект Employee или None.
    """
    stmt = select(Employee).where(Employee.employee_id == employee_id)
    res = await session.execute(stmt)
    employee = res.scalar_one_or_none()
    logger.debug(f"Fetched Employee id={employee_id}: found={employee is not None}")
    return employee


async def get_employees(session: AsyncSession) -> List[Employee]:
    """
    Получить всех сотрудников.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Employee.
    """
    stmt = select(Employee)
    res = await session.execute(stmt)
    employees = res.scalars().all()
    logger.debug(f"Fetched {len(employees)} employees")
    return employees


async def update_employee(
        session: AsyncSession, employee_id: int, data: dict
) -> Optional[Employee]:
    """
    Обновить данные сотрудника.

    Args:
        session: Асинхронная сессия БД.
        employee_id: Идентификатор изменяемого сотрудника.
        data: Словарь с ключом 'name'.

    Returns:
        Обновлённый объект Employee или None.

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
            select(Employee).where(
                Employee.name == new_name,
                Employee.employee_id != employee_id
            )
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Employee with name='{new_name}' already exists")

    stmt = (
        update(Employee)
        .where(Employee.employee_id == employee_id)
        .values(**data)
        .returning(Employee)
    )
    res = await session.execute(stmt)
    employee = res.scalar_one_or_none()
    if employee:
        await session.commit()
        logger.info(f"Updated Employee id={employee_id}")
    else:
        await session.rollback()
        logger.warning(f"Employee id={employee_id} not found for update")
    return employee


async def delete_employee(session: AsyncSession, employee_id: int) -> bool:
    """
    Удалить сотрудника.

    Args:
        session: Асинхронная сессия БД.
        employee_id: Идентификатор удаляемого сотрудника.

    Returns:
        True, если сотрудник был удалён; иначе False.
    """
    stmt = delete(Employee).where(Employee.employee_id == employee_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Employee id={employee_id}")
    else:
        await session.rollback()
        logger.warning(f"Employee id={employee_id} not found for delete")
    return deleted
