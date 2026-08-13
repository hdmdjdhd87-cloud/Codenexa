from __future__ import annotations

from typing import Optional

from app.auth.telegram import TelegramUser
from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def get_or_create_user(tg: TelegramUser) -> dict:
    """
    Идемпотентно находит или создаёт пользователя по telegram_user_id.
    Обновляет профильные поля и last_seen_at при каждом входе — Telegram
    остаётся единственным источником правды для этих данных (п.24).
    """
    pool = get_pool()
    if pool is None:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DATABASE_UNAVAILABLE",
            "База данных временно недоступна. Попробуйте позже.",
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_users
                (telegram_user_id, username, first_name, last_name, language_code, photo_url, last_seen_at)
            values ($1, $2, $3, $4, $5, $6, now())
            on conflict (telegram_user_id) do update set
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                photo_url = excluded.photo_url,
                last_seen_at = now()
            returning id, telegram_user_id, username, first_name, last_name,
                      language_code, photo_url, created_at, updated_at, last_seen_at
            """,
            tg.telegram_user_id,
            tg.username,
            tg.first_name,
            tg.last_name,
            tg.language_code,
            tg.photo_url,
        )
    return dict(row)


async def get_user_by_id(user_id: str) -> Optional[dict]:
    pool = get_pool()
    if pool is None:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "DATABASE_UNAVAILABLE",
            "База данных временно недоступна. Попробуйте позже.",
        )
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select id, telegram_user_id, username, first_name, last_name,
                   language_code, photo_url, created_at, updated_at, last_seen_at
            from nexa_users where id = $1
            """,
            user_id,
        )
    return dict(row) if row else None
