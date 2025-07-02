# -*- coding: utf-8 -*-
# FinFlow/Dockerfile
# ==============================================================================
# Docker image configuration for FinFlow.
# Builds a slim Python environment with Poetry, copies the source code, installs
# dependencies and sets the entrypoint for the bot application.
# ==============================================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_VERSION=1.8.2 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# ------------------------------------------------------------------------------
# Section: System Dependencies
# ------------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl git && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# Section: Poetry installation
# ------------------------------------------------------------------------------
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# ------------------------------------------------------------------------------
# Section: Python Dependencies
# ------------------------------------------------------------------------------
COPY pyproject.toml poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi

# ------------------------------------------------------------------------------
# Section: Application Source
# ------------------------------------------------------------------------------
COPY src /app/src

# ------------------------------------------------------------------------------
# Section: Entrypoint
# ------------------------------------------------------------------------------
CMD ["python", "-m", "src.bot.bot"]