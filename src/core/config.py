# -*- coding: utf-8 -*-
# FinFlow/src/core/config.py
"""
Centralised, type-safe application settings.

Reads variables from `.env.*` or the real environment and exposes them via the
`get_settings()` singleton.  Compatible with Pydantic-Settings ≥2.1.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, List

from dotenv import load_dotenv
from pydantic import Field, PostgresDsn, RedisDsn, ValidationError, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

from src.core.logger import configure_logger

logger = configure_logger(prefix="CFG", color="yellow", level="DEBUG")

# --------------------------------------------------------------------------- #
# .env discovery                                                              #
# --------------------------------------------------------------------------- #
project_root = Path(__file__).resolve().parents[2]
env_dev = project_root / ".env.dev"
env_prod = project_root / ".env.prod"
env_file = env_dev if env_dev.exists() else env_prod if env_prod.exists() else project_root / ".env"

load_dotenv(env_file)
logger.debug(f"Loaded environment variables from {env_file}")


# Кастомный валидатор для преобразования строки в список целых чисел
def parse_int_list(v: str) -> list[int]:
    if not v or v.strip() == "":
        return []

    v = v.strip()

    # ① JSON‑список: "[1,2,3]"
    if v.startswith("[") and v.endswith("]"):
        try:
            return [int(x) for x in json.loads(v)]
        except (json.JSONDecodeError, ValueError):
            pass  # если не получилось – пробуем как CSV ниже

    # ② Простой CSV: "1,2,3"
    try:
        return [int(x.strip()) for x in v.split(",") if x.strip()]
    except ValueError:
        # ③ На всякий случай: извлекаем все цифры регуляркой "1; 2 ; 3"
        numbers = re.findall(r"\d+", v)
        if numbers:
            return list(map(int, numbers))

    raise ValueError(
        f"Invalid format for list, expected [1,2] or '1,2', got: {v}"
    )


IntList = Annotated[List[int], BeforeValidator(parse_int_list)]


# --------------------------------------------------------------------------- #
# Settings definition                                                         #
# --------------------------------------------------------------------------- #
class Settings(BaseSettings):
    """Project-wide strongly-typed config."""

    model_config = SettingsConfigDict(case_sensitive=True)

    # ---- Core ------------------------------------------------------------- #
    env: Literal["dev", "prod"] = Field("dev", alias="ENV")
    debug: bool = Field(False, alias="DEBUG")

    # ---- PostgreSQL ------------------------------------------------------- #
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_host: str = Field(..., alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    # ---- Redis ------------------------------------------------------------ #
    redis_user: str = Field("default", alias="REDIS_USER")
    redis_password: str = Field(..., alias="REDIS_PASSWORD")
    redis_host: str = Field(..., alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")

    # ---- Bot -------------------------------------------------------------- #
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # ---- Article Codes ---------------------------------------------------- #
    income_article_codes_raw: str = Field(..., alias="INCOME_ARTICLE_CODES")
    project_outcome_article_codes_raw: str = Field(..., alias="PROJECT_OUTCOME_ARTICLE_CODES")
    operational_outcome_article_codes_raw: str = Field(..., alias="OPERATIONAL_OUTCOME_ARTICLE_CODES")
    financial_outcome_article_codes_raw: str = Field(..., alias="FINANCIAL_OUTCOME_ARTICLE_CODES")

    # ---- Computed --------------------------------------------------------- #

    @property
    def database_url(self) -> str:
        """
        AsyncPG DSN (SQLAlchemy format).

        Собираем вручную, чтобы избежать двойного "//" в пути:
        postgresql+asyncpg://user:password@host:port/dbname
        """
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis DSN with AUTH."""
        return RedisDsn.build(
            scheme="redis",
            password=self.redis_password,
            host=self.redis_host,
            port=str(self.redis_port),
            path="0",  # база 0
        )

    @property
    def income_article_codes(self) -> list[int]:
        return parse_int_list(self.income_article_codes_raw)

    @property
    def project_outcome_article_codes(self) -> list[int]:
        return parse_int_list(self.project_outcome_article_codes_raw)

    @property
    def operational_outcome_article_codes(self) -> list[int]:
        return parse_int_list(self.operational_outcome_article_codes_raw)

    @property
    def financial_outcome_article_codes(self) -> list[int]:
        return parse_int_list(self.financial_outcome_article_codes_raw)


# --------------------------------------------------------------------------- #
# Singleton accessor                                                         #
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError as exc:  # pragma: no cover
        logger.error(f"Invalid env config: {exc}")
        raise

    logger.info(
        f"env={settings.env} debug={settings.debug} "
        f"db={settings.postgres_user}@{settings.postgres_host}:"
        f"{settings.postgres_port}/{settings.postgres_db}"
    )
    return settings