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


async def list_notifications(user_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, type, title, message, module_id, is_read, created_at
            from nexa_notifications
            where user_id = $1
            order by created_at desc
            """,
            user_id,
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
