from __future__ import annotations

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def list_projects(user_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select id, name, description, icon, accent, created_at, updated_at "
            "from nexa_projects where user_id = $1 order by created_at desc",
            user_id,
        )
    return [dict(r) for r in rows]
