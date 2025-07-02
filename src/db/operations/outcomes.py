# -*- coding: utf-8 -*-
# FinFlow/src/db/models/outcomes.py
"""
Модель `Outcome` и CRUD‑методы для управления расходными операциями.

Содержит:
    • ORM‑модель `Outcome` с широким набором полей для детализации расходов:
      кошелек или кредитор-источник, раздел и статья выбытия, сотрудник, материал,
      подрядчик, учредитель и отдельная статья для кредитора (статья 29).
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей расходных операций с подробным логированием.

Особенности:
    - `outcome_founder` обязателен для статей 29 и 30.
    - `outcome_article_creditor` обязателен для статьи 29.
    - `operation_amount` должен быть не больше 0 (отрицательный или 0).
    - `outcome_chapter` связан с проектом и может быть NULL или содержать project_id.
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Date, DateTime, Integer, Numeric
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from src.db.service.base import Base
from src.db.models.creditors import Creditor
from src.db.models.projects import Project
from src.core.logger import configure_logger
from src.db.models.wallets import Wallet

logger = configure_logger(prefix="OUTCOMES", color="red", level="INFO")

# --------------------------------------------------------------------------- #
# Outcome Model                                                               #
# --------------------------------------------------------------------------- #


class Outcome(Base):
    """ORM‑модель расходной операции."""

    __tablename__ = "outcomes"

    transaction_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    recording_date: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    operation_date: Mapped[_dt.date] = mapped_column(Date, nullable=False, index=True)

    # источник списания: либо кошелек, либо кредитор
    outcome_wallet: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("wallets.wallet_id"), nullable=True, index=True
    )
    outcome_creditor: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("creditors.creditor_id"), nullable=True, index=True
    )

    # Связь с проектом (может быть NULL или project_id)
    outcome_chapter: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.project_id"), nullable=True, index=True
    )

    outcome_article: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.article_id"), nullable=False
    )

    # детализация для статей 3,4,7,8,11
    employee_name: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.employee_id"), nullable=True
    )
    material_name: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("materials.material_id"), nullable=True
    )
    contractor_name: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("contractors.contractor_id"), nullable=True
    )

    # для статей 29,30
    outcome_founder: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("founders.founder_id"), nullable=True, index=True
    )
    # отдельная категория выплат по кредитам (статья 29)
    outcome_article_creditor: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    operation_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Всегда отрицательное или нулевое значение; бизнес‑логика задаёт знак.",
    )
    operation_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # отношения
    wallet = relationship("Wallet", back_populates="outcomes", lazy="joined")
    creditor = relationship("Creditor", back_populates="outcomes", lazy="joined")
    project = relationship("Project", back_populates="outcomes")
    article = relationship("Article", back_populates="outcomes")
    employee = relationship("Employee", back_populates="outcomes")
    material = relationship("Material", back_populates="outcomes")
    contractor = relationship("Contractor", back_populates="outcomes")
    founder = relationship("Founder", back_populates="outcomes")

    __table_args__ = (
        CheckConstraint(
            "operation_amount <= 0", name="ck_outcome_amount_nonpositive"
        ),
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_outcome(session: AsyncSession, data: dict) -> Outcome:
    """
    Создать запись расхода.

    Args:
        session: Открытая асинхронная сессия.
        data: Словарь полей, совместимый с моделью Outcome.

    Returns:
        Объект Outcome после коммита.

    Raises:
        ValueError: При некорректной сумме, отсутствии обязательных полей или неверном project_id.
        SQLAlchemyError: Любые ошибки слоя БД.
    """
    amount = data.get("operation_amount")
    if amount is None or amount > 0:
        raise ValueError("operation_amount must be non‑positive (<= 0)")

    article = data.get("outcome_article")

    # Валидация outcome_chapter
    if "outcome_chapter" in data:
        if data["outcome_chapter"] is not None:
            project = await session.get(Project, data["outcome_chapter"])
            if not project:
                raise ValueError(f"Project id={data['outcome_chapter']} does not exist")

    # преобразование дат
    if isinstance(data.get("recording_date"), str):
        data["recording_date"] = _dt.datetime.fromisoformat(data["recording_date"])
    if isinstance(data.get("operation_date"), str):
        data["operation_date"] = _dt.datetime.strptime(
            data["operation_date"], "%d.%m.%Y"
        ).date()

    # проверка наличия кошелька/кредитора
    if data.get("outcome_wallet"):
        if await session.get(Wallet, data["outcome_wallet"]) is None:
            raise ValueError(f"Wallet '{data['outcome_wallet']}' does not exist")
    if data.get("outcome_creditor"):
        if await session.get(Creditor, data["outcome_creditor"]) is None:
            raise ValueError(f"Creditor id={data['outcome_creditor']} does not exist")

    outcome = Outcome(**data)
    session.add(outcome)
    await session.flush()
    await session.commit()
    logger.info(f"Created Outcome id={outcome.transaction_id}")
    return outcome


async def get_outcome(session: AsyncSession, transaction_id: int) -> Optional[Outcome]:
    """
    Получить расход по ID.

    Args:
        session: Асинхронная сессия.
        transaction_id: Первичный ключ.

    Returns:
        Outcome или None.
    """
    stmt = select(Outcome).where(Outcome.transaction_id == transaction_id)
    res = await session.execute(stmt)
    outcome = res.scalar_one_or_none()
    logger.debug(
        f"Fetched Outcome id={transaction_id}: found={outcome is not None}"
    )
    return outcome


async def update_outcome(
    session: AsyncSession, transaction_id: int, data: dict
) -> Optional[Outcome]:
    """
    Обновить запись расхода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID изменяемой записи.
        data: Поля для обновления.

    Returns:
        Изменённый объект Outcome или None.
    """
    if "operation_amount" in data and data["operation_amount"] > 0:
        raise ValueError("operation_amount must remain non‑positive (<= 0)")

    if "outcome_article" in data:
        art = data["outcome_article"]
        if art in (29, 30) and not data.get("outcome_founder"):
            raise ValueError("outcome_founder is required for articles 29 and 30")
        if art == 29 and not data.get("outcome_article_creditor"):
            raise ValueError("outcome_article_creditor is required for article 29")

    # Валидация outcome_chapter
    if "outcome_chapter" in data:
        if data["outcome_chapter"] is not None:
            project = await session.get(Project, data["outcome_chapter"])
            if not project:
                raise ValueError(f"Project id={data['outcome_chapter']} does not exist")

    stmt = (
        update(Outcome)
        .where(Outcome.transaction_id == transaction_id)
        .values(**data)
        .returning(Outcome)
    )
    res = await session.execute(stmt)
    outcome = res.scalar_one_or_none()
    if outcome:
        await session.commit()
        logger.info(f"Updated Outcome id={transaction_id}")
    else:
        logger.warning(f"Outcome id={transaction_id} not found for update")
    return outcome


async def delete_outcome(session: AsyncSession, transaction_id: int) -> bool:
    """
    Удалить запись расхода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID удаляемой записи.

    Returns:
        True, если запись удалена.
    """
    stmt = delete(Outcome).where(Outcome.transaction_id == transaction_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Outcome id={transaction_id}")
    else:
        logger.warning(f"Outcome id={transaction_id} not found for delete")
    return deleted