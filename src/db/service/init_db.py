# -*- coding: utf-8 -*-
# FinFlow/src/db/init_db.py
import asyncio

from src.db.service.base import Base        # Declarative Base + все модели зарегистрированы
from src.db.service.session import engine      # AsyncEngine
from src.core.logger import configure_logger

logger = configure_logger(prefix="INIT_DB", color="magenta")

async def init_models() -> None:
    logger.info("Creating all tables in database…")
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables created successfully.")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(init_models())
