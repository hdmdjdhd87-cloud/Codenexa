from __future__ import annotations

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def list_favorites(user_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select f.id, f.module_id, f.created_at,
                   m.module_key, m.name, m.description, m.category, m.icon, m.route, m.status
            from nexa_favorites f
            join nexa_modules m on m.id = f.module_id
            where f.user_id = $1
            order by f.created_at desc
            """,
            user_id,
        )
    return [dict(r) for r in rows]


async def add_favorite(user_id: str, module_id: str) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_favorites (user_id, module_id)
            values ($1, $2)
            on conflict (user_id, module_id) do update set user_id = excluded.user_id
            returning id, module_id, created_at
            """,
            user_id,
            module_id,
        )
    return dict(row)


async def remove_favorite(user_id: str, module_id: str) -> None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        await conn.execute(
            "delete from nexa_favorites where user_id = $1 and module_id = $2",
            user_id,
            module_id,
        )
