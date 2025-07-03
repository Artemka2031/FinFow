# -*- coding: utf-8 -*-
# FinFlow/Dockerfile
# ------------------------------------------------------------------------------
# Сборка slim‑образа с поддержкой ru_RU.UTF‑8 и часовым поясом Europe/Moscow
# ------------------------------------------------------------------------------

FROM python:3.13.2-slim AS base
WORKDIR /app

# ──────────────────────────── System deps + locale + TZ ───────────────────────
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        git bash locales tzdata; \
    \
    # включаем en_US и ru_RU в /etc/locale.gen
    sed -Ei 's/^# *((en_US|ru_RU)\.UTF-8)/\1/' /etc/locale.gen; \
    locale-gen; \
    \
    # московский часовой пояс
    ln -snf /usr/share/zoneinfo/Europe/Moscow /etc/localtime; \
    echo "Europe/Moscow" > /etc/timezone; \
    \
    apt-get clean; rm -rf /var/lib/apt/lists/*

# ─────────────────────────────── Env vars ─────────────────────────────────────
ENV LANG=ru_RU.UTF-8 \
    LANGUAGE=ru_RU:ru \
    LC_ALL=ru_RU.UTF-8 \
    TZ=Europe/Moscow \
    POETRY_VERSION=2.1.3 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

# ─────────────────────────── Poetry + deps ────────────────────────────────────
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"
COPY pyproject.toml poetry.lock* /app/
RUN poetry config virtualenvs.create $POETRY_VIRTUALENVS_CREATE && \
    poetry lock && \
    poetry install --no-interaction --no-ansi --no-root

# ─────────────────────────── Source code ──────────────────────────────────────
COPY src /app/src

# ─────────────────────────── Entrypoint ───────────────────────────────────────
CMD ["python", "-m", "src.bot.bot"]
