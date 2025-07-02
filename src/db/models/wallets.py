# -*- coding: utf-8 -*-
# FinFlow/src/db/wallets.py
"""
Справочник `Wallet` и CRUD‑методы для управления финансовыми кошельками.

Содержит:
    • ORM‑модель `Wallet` с полями `wallet_id` и `wallet_number`.
    • Обратные связи с моделями `Income`, `Outcome`, `Transfer`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей кошельков с логированием и валидацией данных.

Кошельки используются во всех типах операций: приходы, переводы, выбытия.
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy import String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from src.db.service.base import Base
from src.core.logger import configure_logger

logger = configure_logger(prefix="WALLETS", color="blue", level="INFO")

# --------------------------------------------------------------------------- #
# Wallet Model                                                                #
# --------------------------------------------------------------------------- #


class Wallet(Base):
    """ORM‑модель финансового кошелька."""

    __tablename__ = "wallets"

    wallet_id: Mapped[str] = mapped_column(
        String(50), primary_key=True, doc="Уникальный идентификатор кошелька"
    )
    wallet_number: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, doc="Номер или адрес кошелька"
    )

    # обратные отношения
    incomes = relationship("Income", back_populates="wallet", lazy="selectin")
    outcomes = relationship("Outcome", back_populates="wallet", lazy="selectin")
    incoming_transfers = relationship(
        "Transfer",
        back_populates="wallet_to",
        foreign_keys="[Transfer.to_wallet]",  # Указываем конкретный внешний ключ
        lazy="selectin"
    )
    outgoing_transfers = relationship(
        "Transfer",
        back_populates="wallet_from",
        foreign_keys="[Transfer.from_wallet]",  # Указываем конкретный внешний ключ
        lazy="selectin"
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_wallet(
    session: AsyncSession, wallet_id: str, wallet_number: str
) -> Wallet:
    """
    Создать новый кошелек.

    Args:
        session: Асинхронная сессия БД.
        wallet_id: Уникальный идентификатор (строка).
        wallet_number: Номер или адрес кошелька (строка).

    Returns:
        Созданный объект Wallet.

    Raises:
        ValueError: При неверном формате wallet_number.
        IntegrityError: Если wallet_id или wallet_number уже существуют.
    """
    # Валидация формата номера: буквы (латинские/кириллические), цифры, пробелы, -, _, ., ,
    if not wallet_number or len(wallet_number) > 100 or not re.match(r'^[\w\s\-\.,\u0400-\u04FF]+$', wallet_number):
        raise ValueError(
            "wallet_number должен быть непустым, ≤100 chars, allowed: letters (Latin/Cyrillic), digits, spaces, '-', '_', '.', ','"
        )

    wallet = Wallet(wallet_id=wallet_id, wallet_number=wallet_number)
    session.add(wallet)
    try:
        await session.flush()
        await session.commit()
        logger.info(f"Created Wallet id={wallet_id}")
        return wallet
    except IntegrityError as exc:
        await session.rollback()
        logger.error(f"Failed to create Wallet id={wallet_id}: {exc}")
        raise


async def get_wallet(
    session: AsyncSession, wallet_id: str
) -> Optional[Wallet]:
    """
    Получить кошелек по его ID.

    Args:
        session: Асинхронная сессия БД.
        wallet_id: Идентификатор кошелька.

    Returns:
        Объект Wallet или None.
    """
    stmt = select(Wallet).where(Wallet.wallet_id == wallet_id)
    res = await session.execute(stmt)
    wallet = res.scalar_one_or_none()
    logger.debug(f"Fetched Wallet id={wallet_id}: found={wallet is not None}")
    return wallet


async def get_wallets(session: AsyncSession) -> List[Wallet]:
    """
    Получить список всех кошельков.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список объектов Wallet.
    """
    stmt = select(Wallet)
    res = await session.execute(stmt)
    wallets = res.scalars().all()
    logger.debug(f"Fetched {len(wallets)} wallets")
    return wallets


async def update_wallet(
    session: AsyncSession, wallet_id: str, data: dict
) -> Optional[Wallet]:
    """
    Обновить данные кошелька.

    Args:
        session: Асинхронная сессия БД.
        wallet_id: Идентификатор существующего кошелька.
        data: Словарь с ключами: 'wallet_number'.

    Returns:
        Обновлённый объект Wallet или None.
    """
    if "wallet_number" in data:
        if not re.match(r'^[A-Za-z0-9_-]+$', data["wallet_number"]):
            raise ValueError(
                "wallet_number должен содержать только латинские буквы, цифры, '-' или '_'"
            )

    stmt = (
        update(Wallet)
        .where(Wallet.wallet_id == wallet_id)
        .values(**data)
        .returning(Wallet)
    )
    res = await session.execute(stmt)
    wallet = res.scalar_one_or_none()
    if wallet:
        await session.commit()
        logger.info(f"Updated Wallet id={wallet_id}")
    else:
        await session.rollback()
        logger.warning(f"Wallet id={wallet_id} not found for update")
    return wallet


async def delete_wallet(session: AsyncSession, wallet_id: str) -> bool:
    """
    Удалить кошелек.

    Args:
        session: Асинхронная сессия БД.
        wallet_id: Идентификатор удаляемого кошелька.

    Returns:
        True, если кошелек был удалён, иначе False.
    """
    stmt = delete(Wallet).where(Wallet.wallet_id == wallet_id)
    res = await session.execute(stmt)
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Wallet id={wallet_id}")
    else:
        await session.rollback()
        logger.warning(f"Wallet id={wallet_id} not found for delete")
    return deleted
