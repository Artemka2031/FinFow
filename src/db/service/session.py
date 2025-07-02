# -*- coding: utf-8 -*-
# FinFlow/src/db/session.py
"""
Асинхронный движок и сессии для FinFlow.

* Создаёт AsyncEngine.
* Делает async_sessionmaker.
* Предоставляет async‑контекст‑генератор get_async_session().
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from src.core.config import get_settings
from src.core.logger import configure_logger

logger = configure_logger(prefix="DB", color="cyan", level="INFO")

# --------------------------------------------------------------------------- #
# Engine / Session factory                                                   #
# --------------------------------------------------------------------------- #
_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    # echo=_settings.debug,
    pool_pre_ping=True,
)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)

# --------------------------------------------------------------------------- #
# Dependency helper                                                          #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный контекст‑генератор сессии.

    Usage:
        async with get_async_session() as session:
            # ваш код
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Session rollback due to exception")
            raise
