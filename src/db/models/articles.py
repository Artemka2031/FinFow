# -*- coding: utf-8 -*-
# FinFlow/src/db/models/articles.py
"""
Справочник `Article` и CRUD‑методы для управления классификационными статьями (OPIU).

Содержит:
    • ORM‑модель `Article` с полями `article_id`, `code`, `name`, `short_name`.
    • Обратные связи с моделями `Income` и `Outcome`.
    • Асинхронные CRUD‑функции для создания, чтения, обновления и удаления
      записей статей с логированием и валидацией.

Каждая статья имеет уникальный числовой код (1–35), наименование и короткое имя (до 48 символов).
"""

# --------------------------------------------------------------------------- #
# Imports & logger                                                            #
# --------------------------------------------------------------------------- #
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import select, update, delete

from src.db.service.base import Base
from src.core.logger import configure_logger

logger = configure_logger(prefix="ARTICLES", color="blue", level="INFO")

# --------------------------------------------------------------------------- #
# Article Model                                                               #
# --------------------------------------------------------------------------- #


class Article(Base):
    """ORM‑модель статьи классификации операций."""

    __tablename__ = "articles"

    article_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    code: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False,
        doc="Уникальный код статьи (1–35)"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Название статьи"
    )
    short_name: Mapped[str] = mapped_column(
        String(48), nullable=False,
        doc="Короткое название статьи (до 48 символов)"
    )

    incomes = relationship("Income", back_populates="article", lazy="selectin")
    outcomes = relationship("Outcome", back_populates="article", lazy="selectin")

    __table_args__ = (
        CheckConstraint("code BETWEEN 1 AND 35", name="ck_article_code_range"),
    )


# --------------------------------------------------------------------------- #
# CRUD Methods                                                                #
# --------------------------------------------------------------------------- #
async def create_article(
    session: AsyncSession, code: int, short_name: str, name: str
) -> Article:
    """
    Создать новую статью.

    Args:
        session: Асинхронная сессия БД.
        code: Уникальный числовой код (1–35).
        short_name: Короткое наименование статьи (до 48 символов).
        name: Полное наименование статьи.

    Returns:
        Созданный объект Article.

    Raises:
        ValueError: Если код вне диапазона, short_name > 48 символов или уже существует.
        SQLAlchemyError: При ошибках БД.
    """
    if not (1 <= code <= 35):
        raise ValueError("code must be between 1 and 35")
    if len(short_name) > 48:
        raise ValueError("short_name must be ≤ 48 characters")

    # Проверка дубликата
    existing = await session.execute(
        select(Article).where(Article.code == code)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Article with code={code} already exists")

    article = Article(code=code, short_name=short_name, name=name)
    session.add(article)
    await session.flush()
    await session.commit()
    logger.info(f"Created Article id={article.article_id} code={code}")
    return article


async def get_article(
    session: AsyncSession, article_id: int
) -> Optional[Article]:
    """
    Получить статью по ID.

    Args:
        session: Асинхронная сессия БД.
        article_id: Идентификатор статьи.

    Returns:
        Article или None.
    """
    res = await session.execute(
        select(Article).where(Article.article_id == article_id)
    )
    article = res.scalar_one_or_none()
    logger.debug(f"Fetched Article id={article_id}: found={article is not None}")
    return article


async def get_articles(session: AsyncSession) -> List[Article]:
    """
    Получить все статьи.

    Args:
        session: Асинхронная сессия БД.

    Returns:
        Список Article.
    """
    res = await session.execute(select(Article))
    articles = res.scalars().all()
    logger.debug(f"Fetched {len(articles)} articles")
    return articles


async def update_article(
    session: AsyncSession, article_id: int, data: dict
) -> Optional[Article]:
    """
    Обновить статью.

    Args:
        session: Асинхронная сессия БД.
        article_id: ID изменяемой статьи.
        data: Словарь с полями 'code', 'short_name' и/или 'name'.

    Returns:
        Обновлённый Article или None.

    Raises:
        ValueError: При неверном коде, дубликате или short_name > 48 символов.
    """
    if "code" in data:
        new_code = data["code"]
        if not (1 <= new_code <= 35):
            raise ValueError("code must be between 1 and 35")
        dup = await session.execute(
            select(Article).where(Article.code == new_code, Article.article_id != article_id)
        )
        if dup.scalar_one_or_none():
            raise ValueError(f"Article with code={new_code} already exists")

    if "short_name" in data and len(data["short_name"]) > 48:
        raise ValueError("short_name must be ≤ 48 characters")

    stmt = (
        update(Article)
        .where(Article.article_id == article_id)
        .values(**data)
        .returning(Article)
    )
    res = await session.execute(stmt)
    article = res.scalar_one_or_none()
    if article:
        await session.commit()
        logger.info(f"Updated Article id={article_id}")
    else:
        logger.warning(f"Article id={article_id} not found for update")
    return article


async def delete_article(
    session: AsyncSession, article_id: int
) -> bool:
    """
    Удалить статью.

    Args:
        session: Асинхронная сессия БД.
        article_id: ID удаляемой статьи.

    Returns:
        True, если удаление выполнено.
    """
    res = await session.execute(
        delete(Article).where(Article.article_id == article_id)
    )
    deleted = res.rowcount > 0
    if deleted:
        await session.commit()
        logger.info(f"Deleted Article id={article_id}")
    else:
        await session.rollback()
        logger.warning(f"Article id={article_id} not found for delete")
    return deleted