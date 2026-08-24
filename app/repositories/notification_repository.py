from __future__ import annotations

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def create_notification(user_id: str, type_: str, title: str, message: str, module_id: str | None = None) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_notifications (user_id, type, title, message, module_id)
            values ($1, $2, $3, $4, $5)
            returning id, type, title, message, module_id, is_read, created_at
            """,
            user_id,
            type_,
            title,
            message,
            module_id,
        )
    return dict(row)


async def list_notifications(user_id: str, page: int = 1, page_size: int = 50) -> list[dict]:
    pool = await _pool_or_503()
    # P2 из аудита 22.08.2026: список уведомлений растёт со временем
    # (генерируется системой, не только пользователем) — без границы
    # рано или поздно вернул бы весь накопленный объём одним ответом.
    page_size = max(1, min(page_size, 200))
    offset = max(0, page - 1) * page_size
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, type, title, message, module_id, is_read, created_at
            from nexa_notifications
            where user_id = $1
            order by created_at desc
            limit $2 offset $3
            """,
            user_id,
            page_size,
            offset,
        )
    return [dict(r) for r in rows]


async def mark_read(user_id: str, notification_id: str) -> None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        await conn.execute(
            "update nexa_notifications set is_read = true where id = $1 and user_id = $2",
            notification_id,
            user_id,
        )


async def mark_all_read(user_id: str) -> None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        await conn.execute(
            "update nexa_notifications set is_read = true where user_id = $1 and is_read = false",
            user_id,
        )
