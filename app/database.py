"""
Пул подключений к PostgreSQL (существующий Supabase Postgres).

Важно: этот модуль НЕ трогает и не создаёт старые таблицы проекта.
Все запросы из репозиториев CodeNexa System работают только с
таблицами nexa_* (см. migrations/0001_nexa_core.sql).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

import asyncpg

from app.config import get_settings

logger = logging.getLogger("codenexa.database")

_pool: Optional[asyncpg.Pool] = None


def extract_supabase_project_ref(database_url: str) -> Optional[str]:
    """
    Достаёт Supabase project ref из Postgres DSN — из хоста
    (db.<ref>.supabase.co, прямое подключение :5432) или из имени
    пользователя (postgres.<ref>, подключение через Supavisor pooler
    :6543 — судя по комментариям ниже, именно так проект и настроен).
    Возвращает None, если DSN не похож на Supabase (например, локальная
    БД в разработке) — тогда safety-проверка ниже просто не применяется,
    а не падает вслепую.
    """
    if not database_url:
        return None
    try:
        parsed = urlparse(database_url)
    except ValueError:
        return None

    host = parsed.hostname or ""
    match = re.match(r"^db\.([a-z0-9]+)\.supabase\.co$", host)
    if match:
        return match.group(1)

    username = parsed.username or ""
    match = re.match(r"^postgres\.([a-z0-9]+)$", username)
    if match:
        return match.group(1)

    return None


def _safe_fingerprint(project_ref: Optional[str]) -> str:
    """Для логов — НИКОГДА не пишем полный DSN (там пароль!) или сырой
    ref целиком, только короткий фингерпринт для сверки на глаз."""
    if not project_ref:
        return "unknown/non-supabase"
    if len(project_ref) <= 8:
        return project_ref
    return f"{project_ref[:4]}…{project_ref[-4:]}"


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

    project_ref = extract_supabase_project_ref(settings.database_url)
    logger.info("Подключение к БД — Supabase project fingerprint: %s", _safe_fingerprint(project_ref))

    # SEC-002 (production-аудит 22.08.2026): README/.env.example раньше
    # указывали project ref, отличающийся от реально используемого, и
    # никакой автоматической проверки при этом не было — рассинхрон
    # обнаружился бы только по факту (не те данные читаются/пишутся).
    # Fail-fast вместо этого: если ops явно задал EXPECTED_DB_PROJECT_REF,
    # а реальный DATABASE_URL на него не похож — падаем на старте, а не
    # тихо продолжаем работать не с той БД (перепутанные production/
    # staging окружения). Без этой переменной проверка не блокирует
    # существующие деплои.
    if settings.expected_db_project_ref and project_ref and settings.expected_db_project_ref != project_ref:
        raise RuntimeError(
            "КРИТИЧНО: DATABASE_URL указывает на другой Supabase project, чем ожидалось "
            f"(EXPECTED_DB_PROJECT_REF={_safe_fingerprint(settings.expected_db_project_ref)}, "
            f"фактически={_safe_fingerprint(project_ref)}). Похоже на перепутанное "
            "production/staging окружение. Подключение отклонено — проверьте DATABASE_URL."
        )

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
