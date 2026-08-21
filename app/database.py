"""
Пул подключений к PostgreSQL (существующий Supabase Postgres).

Важно: этот модуль НЕ трогает и не создаёт старые таблицы проекта.
Все запросы из репозиториев CodeNexa System работают только с
таблицами nexa_* (см. migrations/0001_nexa_core.sql).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg

from app.config import get_settings

logger = logging.getLogger("codenexa.database")

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    # КРИТИЧНО: без этого asyncpg возвращает jsonb-колонки как СЫРУЮ
    # строку, а не распарсенный Python-объект.
    for pg_type in ("jsonb", "json"):
        await conn.set_type_codec(
            pg_type,
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )


async def connect() -> None:
    global _pool
    settings = get_settings()
    if not settings.database_url:
        logger.warning(
            "DATABASE_URL не задан — приложение стартует без подключения к БД. "
            "Эндпоинты, требующие базу, будут возвращать 503."
        )
        return
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=10,
            # Supabase PostgreSQL требует TLS для внешних подключений.
            # Явно включаем SSL, чтобы одинаково работать с прямым
            # подключением :5432 и Supavisor pooler :6543.
            ssl="require",
            # Для Supabase/Supavisor transaction pooler отключаем
            # prepared-statement cache. Это также безопасно для прямого
            # PostgreSQL подключения.
            statement_cache_size=0,
            init=_init_connection,
        )
        logger.info(
            "Пул подключений к PostgreSQL создан "
            "(SSL=require, jsonb-кодек зарегистрирован, statement cache отключён)"
        )
    except Exception:  # noqa: BLE001 — сознательно широкий catch на старте
        logger.exception("Не удалось подключиться к PostgreSQL")
        _pool = None


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool


async def ping() -> bool:
    """Используется /health и /ready — не должен падать при отсутствии пула."""
    if _pool is None:
        return False
    try:
        async with _pool.acquire() as conn:
            await conn.execute("select 1")
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Database ping failed")
        return False
