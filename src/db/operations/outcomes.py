# -*- coding: utf-8 -*-
# FinFlow/src/db/models/outcomes.py
"""
Модель `Outcome` и CRUD‑методы для управления расходными операциями.

Новое:
    • Поле `saving_coeff` (коэффициент экономии, 0 ≤ значение ≤ 1).

Особенности:
    - `outcome_founder` обязателен для статей 29 и 30.
    - `outcome_article_creditor` обязателен для статьи 29.
    - `operation_amount` ≤ 0.
    - `saving_coeff` ∈ [0, 1].
    - `outcome_chapter` связан с `Project` и может быть NULL.
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
    select,
    update,
    delete,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.sqltypes import Date, DateTime, Integer, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.service.base import Base
from src.db.models.creditors import Creditor
from src.db.models.projects import Project
from src.db.models.wallets import Wallet
from src.core.logger import configure_logger

logger = configure_logger(prefix="OUTCOMES", color="red", level="INFO")

# --------------------------------------------------------------------------- #
# Outcome Model                                                               #
# --------------------------------------------------------------------------- #
class Outcome(Base):
    """ORM‑модель расходной операции."""

    __tablename__ = "outcomes"

    transaction_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_date: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    operation_date: Mapped[_dt.date] = mapped_column(Date, nullable=False, index=True)

    # источник списания
    outcome_wallet: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("wallets.wallet_id"), nullable=True, index=True)
    outcome_creditor: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("creditors.creditor_id"), nullable=True, index=True)

    # раздел (проект) или общие
    outcome_chapter: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.project_id"), nullable=True, index=True)

    outcome_article: Mapped[int] = mapped_column(Integer, ForeignKey("articles.article_id"), nullable=False)

    # детализация
    employee_name: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.employee_id"), nullable=True)
    material_name: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("materials.material_id"), nullable=True)
    contractor_name: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("contractors.contractor_id"), nullable=True)

    # для статей 29–30
    outcome_founder: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("founders.founder_id"), nullable=True, index=True)
    outcome_article_creditor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # сумма
    operation_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Всегда отрицательное или нулевое значение."
    )

    # КОЭФФИЦИЕНТ ЭКОНОМИИ (0 .. 1)
    saving_coeff: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        doc="Коэффициент экономии (0 ≤ значение ≤ 1)."
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
        CheckConstraint("operation_amount <= 0", name="ck_outcome_amount_nonpositive"),
        CheckConstraint("saving_coeff IS NULL OR (saving_coeff >= 0 AND saving_coeff <= 1)", name="ck_saving_coeff_range"),
    )

# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_outcome(session: AsyncSession, data: dict) -> Outcome:
    """Создать запись расхода."""
    amount = data.get("operation_amount")
    if amount is None or amount > 0:
        raise ValueError("operation_amount must be non‑positive (<= 0)")

    # валидация коэффициента
    if "saving_coeff" in data and data["saving_coeff"] is not None:
        if not (0 <= data["saving_coeff"] <= 1):
            raise ValueError("saving_coeff must be between 0 and 1")

    # валидация project
    if "outcome_chapter" in data and data["outcome_chapter"] is not None:
        if await session.get(Project, data["outcome_chapter"]) is None:
            raise ValueError(f"Project id={data['outcome_chapter']} does not exist")

    # преобразуем даты
    if isinstance(data.get("recording_date"), str):
        data["recording_date"] = _dt.datetime.fromisoformat(data["recording_date"])
    if isinstance(data.get("operation_date"), str):
        data["operation_date"] = _dt.datetime.strptime(data["operation_date"], "%d.%m.%Y").date()

    # проверяем кошелёк/кредитора
    if wid := data.get("outcome_wallet"):
        if await session.get(Wallet, wid) is None:
            raise ValueError(f"Wallet '{wid}' does not exist")
    if cid := data.get("outcome_creditor"):
        if await session.get(Creditor, cid) is None:
            raise ValueError(f"Creditor id={cid} does not exist")

    outcome = Outcome(**data)
    session.add(outcome)
    await session.flush()
    await session.commit()
    logger.info(f"Created Outcome id={outcome.transaction_id}")
    return outcome


async def get_outcome(session: AsyncSession, transaction_id: int) -> Optional[Outcome]:
    """Получить расход по ID."""
    res = await session.execute(select(Outcome).where(Outcome.transaction_id == transaction_id))
    outcome = res.scalar_one_or_none()
    logger.debug(f"Fetched Outcome id={transaction_id}: found={bool(outcome)}")
    return outcome


async def update_outcome(session: AsyncSession, transaction_id: int, data: dict) -> Optional[Outcome]:
    """Обновить запись расхода."""
    if "operation_amount" in data and data["operation_amount"] > 0:
        raise ValueError("operation_amount must remain non‑positive (<= 0)")

    if "saving_coeff" in data and data["saving_coeff"] is not None:
        if not (0 <= data["saving_coeff"] <= 1):
            raise ValueError("saving_coeff must be between 0 and 1")

    if "outcome_chapter" in data and data["outcome_chapter"] is not None:
        if await session.get(Project, data["outcome_chapter"]) is None:
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
    """Удалить запись расхода."""
    deleted = (await session.execute(delete(Outcome).where(Outcome.transaction_id == transaction_id))).rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Outcome id={transaction_id}")
    else:
        logger.warning(f"Outcome id={transaction_id} not found for delete")
    return deleted
