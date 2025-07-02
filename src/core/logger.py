# -*- coding: utf-8 -*-
# FinFlow/src/core/logger.py

from loguru import logger


def configure_logger(
    prefix: str = "APP",
    color: str = "green",
    level: str = "DEBUG"
) -> logger.__class__:
    """
    Return a customised Loguru logger instance.

    Args:
        prefix: Short label added to every message.
        color: Any Loguru‑supported colour name.
        level: Minimum log level captured by the handler.

    Returns:
        Configured `loguru.logger` instance.
    """

    # Удаляем все существующие хендлеры
    logger.remove()

    # Добавляем единственный нужный хендлер
    logger.add(
        lambda msg: print(msg, end=""),
        level=level,
        format=(
            f"<{color}>{{time:YYYY-MM-DD HH:mm:ss.SSS}}</{color}> | "
            "<b>{level:<4}</b> | "
            "<cyan>{name}:{function}:{line}</cyan> | "
            f"<b>{{message}}</b>"
        ),
        colorize=True,
    )

    return logger
