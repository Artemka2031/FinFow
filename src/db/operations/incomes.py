# -*- coding: utf-8 -*-
# FinFlow/src/db/incomes.py
"""
Модель `Income` и CRUD‑методы для учёта приходных операций.

Содержит:
    • ORM‑модель `Income` с внешними ключами на справочники
      (wallets, articles, projects, creditors, founders).
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей с детальным логированием.

Таблица хранит сведения о поступивших средствах — дату записи (ISO 8601),
дату фактической операции, сумму (знак «+» контролируется бизнес‑логикой) и
пользовательский комментарий.
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Date, DateTime, Integer, Numeric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from src.db.service.base import Base
from src.core.logger import configure_logger

logger = configure_logger(prefix="INCOMES", color="green", level="INFO")

# --------------------------------------------------------------------------- #
# Income Model                                                                #
# --------------------------------------------------------------------------- #


class Income(Base):
    """ORM‑модель поступления средств."""

    __tablename__ = "incomes"

    transaction_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    recording_date: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    operation_date: Mapped[_dt.date] = mapped_column(Date, nullable=False, index=True)

    # --- внешние ключи ---
    income_wallet: Mapped[str] = mapped_column(
        String(50), ForeignKey("wallets.wallet_id"), nullable=False, index=True
    )
    income_article: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.article_id"), nullable=False
    )
    income_project: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.project_id"), nullable=True
    )
    income_creditor: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("creditors.creditor_id"), nullable=True
    )
    income_founder: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("founders.founder_id"), nullable=True
    )

    operation_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Всегда положительное значение; знак «+» задаётся в бизнес‑логике.",
    )
    operation_comment: Mapped[str] = mapped_column(Text, nullable=True)

    # --- отношения (ленивые, чтобы не тянуть всё сразу) ---
    wallet = relationship("Wallet", back_populates="incomes", lazy="joined")
    article = relationship("Article", back_populates="incomes")
    project = relationship("Project", back_populates="incomes")
    creditor = relationship("Creditor", back_populates="incomes")
    founder = relationship("Founder", back_populates="incomes")

    __table_args__ = (
        CheckConstraint("operation_amount >= 0", name="ck_income_amount_positive"),
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_income(session: AsyncSession, data: dict) -> Income:
    """
    Создать запись прихода.

    Args:
        session: Открытая асинхронная сессия.
        data: Словарь полей, совместимый с моделью Income.

    Returns:
        Объект Income после коммита.

    Raises:
        ValueError: Если сумма отрицательная или даты неверного формата.
        SQLAlchemyError: Любая ошибка слоя БД.
    """
    # --- предварительная валидация ---
    amount = data.get("operation_amount")
    if amount is None or amount < 0:
        raise ValueError("operation_amount must be non‑negative")

    # ISO 8601 → datetime
    if isinstance(data.get("recording_date"), str):
        data["recording_date"] = _dt.datetime.fromisoformat(data["recording_date"])

    # dd.mm.yyyy → date
    if isinstance(data.get("operation_date"), str):
        data["operation_date"] = _dt.datetime.strptime(
            data["operation_date"], "%d.%m.%Y"
        ).date()

    income = Income(**data)
    session.add(income)
    await session.flush()  # получить PK
    await session.commit()
    logger.info(f"Created Income id={income.transaction_id}")
    return income


async def get_income(session: AsyncSession, transaction_id: int) -> Optional[Income]:
    """
    Получить приход по ID.

    Args:
        session: Асинхронная сессия.
        transaction_id: Первичный ключ.

    Returns:
        Income или None.
    """
    stmt = select(Income).where(Income.transaction_id == transaction_id)
    res = await session.execute(stmt)
    income = res.scalar_one_or_none()
    logger.debug(f"Fetched Income id={transaction_id}: found={income is not None}")
    return income


async def update_income(
    session: AsyncSession, transaction_id: int, data: dict
) -> Optional[Income]:
    """
    Обновить запись прихода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID изменяемой записи.
        data: Поля для обновления.

    Returns:
        Изменённый объект Income или None.
    """
    if "operation_amount" in data and data["operation_amount"] < 0:
        raise ValueError("operation_amount must remain non‑negative")

    stmt = (
        update(Income)
        .where(Income.transaction_id == transaction_id)
        .values(**data)
        .returning(Income)
    )
    res = await session.execute(stmt)
    income = res.scalar_one_or_none()
    if income:
        await session.commit()
        logger.info(f"Updated Income id={transaction_id}")
    else:
        logger.warning(f"Income id={transaction_id} not found for update")
    return income


async def delete_income(session: AsyncSession, transaction_id: int) -> bool:
    """
    Удалить запись прихода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID удаляемой записи.

    Returns:
        True, если запись удалена.
    """
    stmt = delete(Income).where(Income.transaction_id == transaction_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Income id={transaction_id}")
    else:
        logger.warning(f"Income id={transaction_id} not found for delete")
    return deleted
