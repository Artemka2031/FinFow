# -*- coding: utf-8 -*-
# FinFlow/src/db/transfers.py
"""
Модель `Transfer` и CRUD‑методы для управления переводами между кошельками.

Содержит:
    • ORM‑модель `Transfer` с двумя внешними ключами на справочник `Wallet`
      (откуда и куда переводятся средства).
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей переводов с подробным логированием.

Важно: переводы не влияют на OPIU/DDS, но отражают внутреннее движение средств
между счетами.
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
from src.db.models.wallets import Wallet
from src.core.logger import configure_logger

logger = configure_logger(prefix="TRANSFERS", color="yellow", level="INFO")

# --------------------------------------------------------------------------- #
# Transfer Model                                                              #
# --------------------------------------------------------------------------- #


class Transfer(Base):
    """ORM‑модель внутреннего перевода средств между кошельками."""

    __tablename__ = "transfers"

    transaction_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    recording_date: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    operation_date: Mapped[_dt.date] = mapped_column(Date, nullable=False, index=True)

    to_wallet: Mapped[str] = mapped_column(
        String(50), ForeignKey("wallets.wallet_id"), nullable=False, index=True
    )
    from_wallet: Mapped[str] = mapped_column(
        String(50), ForeignKey("wallets.wallet_id"), nullable=False, index=True
    )

    operation_amount: Mapped[float] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        doc="Сумма без знака; бизнес-логика ответственна за корректный знак.",
    )
    operation_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # отношения к кошелькам
    wallet_to = relationship(
        "Wallet",
        foreign_keys=[to_wallet],
        back_populates="incoming_transfers",
        lazy="joined",
    )
    wallet_from = relationship(
        "Wallet",
        foreign_keys=[from_wallet],
        back_populates="outgoing_transfers",
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint("operation_amount >= 0", name="ck_transfer_amount_nonneg"),
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_transfer(session: AsyncSession, data: dict) -> Transfer:
    """
    Создать запись перевода.

    Args:
        session: Открытая асинхронная сессия.
        data: Словарь полей, совместимый с моделью Transfer.

    Returns:
        Объект Transfer после коммита.

    Raises:
        ValueError: Если сумма отрицательная или кошельки не существуют.
        SQLAlchemyError: При ошибках БД.
    """
    amount = data.get("operation_amount")
    if amount is None or amount < 0:
        raise ValueError("operation_amount must be non‑negative")

    # Проверка существования кошельков
    to_id = data.get("to_wallet")
    from_id = data.get("from_wallet")
    for wallet_id, role in ((to_id, "to_wallet"), (from_id, "from_wallet")):
        wallet = await session.get(Wallet, wallet_id)
        if wallet is None:
            raise ValueError(f"Wallet {role}='{wallet_id}' does not exist")

    # Преобразование дат
    if isinstance(data.get("recording_date"), str):
        data["recording_date"] = _dt.datetime.fromisoformat(data["recording_date"])
    if isinstance(data.get("operation_date"), str):
        data["operation_date"] = _dt.datetime.strptime(
            data["operation_date"], "%d.%m.%Y"
        ).date()

    transfer = Transfer(**data)
    session.add(transfer)
    await session.flush()
    await session.commit()
    logger.info(
        f"Created Transfer id={transfer.transaction_id} "
        f"from={from_id} to={to_id} amount={transfer.operation_amount}"
    )
    return transfer


async def get_transfer(session: AsyncSession, transaction_id: int) -> Optional[Transfer]:
    """
    Получить перевод по ID.

    Args:
        session: Асинхронная сессия.
        transaction_id: Первичный ключ.

    Returns:
        Transfer или None.
    """
    stmt = select(Transfer).where(Transfer.transaction_id == transaction_id)
    res = await session.execute(stmt)
    transfer = res.scalar_one_or_none()
    logger.debug(
        f"Fetched Transfer id={transaction_id}: found={transfer is not None}"
    )
    return transfer


async def update_transfer(
    session: AsyncSession, transaction_id: int, data: dict
) -> Optional[Transfer]:
    """
    Обновить запись перевода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID изменяемой записи.
        data: Поля для обновления.

    Returns:
        Изменённый объект Transfer или None.
    """
    if "operation_amount" in data and data["operation_amount"] < 0:
        raise ValueError("operation_amount must remain non‑negative")

    # Проверяем кошельки, если они меняются
    for field in ("to_wallet", "from_wallet"):
        if field in data:
            wallet = await session.get(Wallet, data[field])
            if wallet is None:
                raise ValueError(f"Wallet {field}='{data[field]}' does not exist")

    stmt = (
        update(Transfer)
        .where(Transfer.transaction_id == transaction_id)
        .values(**data)
        .returning(Transfer)
    )
    res = await session.execute(stmt)
    transfer = res.scalar_one_or_none()
    if transfer:
        await session.commit()
        logger.info(f"Updated Transfer id={transaction_id}")
    else:
        logger.warning(f"Transfer id={transaction_id} not found for update")
    return transfer


async def delete_transfer(session: AsyncSession, transaction_id: int) -> bool:
    """
    Удалить запись перевода.

    Args:
        session: Асинхронная сессия.
        transaction_id: ID удаляемой записи.

    Returns:
        True, если запись удалена.
    """
    stmt = delete(Transfer).where(Transfer.transaction_id == transaction_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Transfer id={transaction_id}")
    else:
        logger.warning(f"Transfer id={transaction_id} not found for delete")
    return deleted
