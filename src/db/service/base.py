# -*- coding: utf-8 -*-
# FinFlow/src/db/base.py
"""
Базовые конструкции ORM‑слоя FinFlow.

* Определяет Declarative‑базу (`Base`) для всех моделей.
* Содержит только описание Base и repr, без импорта моделей.
"""

from __future__ import annotations
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Common parent for all ORM‑models."""

    repr_cols_num = 3  # truncate __repr__ to first N columns

    def __repr__(self) -> str:  # pragma: no cover
        cols = list(self.__mapper__.columns)
        body = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in cols[: self.repr_cols_num]
        )
        if len(cols) > self.repr_cols_num:
            body += ", …"
        return f"<{self.__class__.__name__}({body})>"
