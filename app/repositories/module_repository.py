from __future__ import annotations

from typing import Optional

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def list_active_modules() -> list[dict]:
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, module_key, name, slug, description, category, icon, route,
                   version, status, is_featured, sort_order, created_at, updated_at
            from nexa_modules
            where status != 'disabled'
            order by sort_order asc, name asc
            """
        )
    return [dict(r) for r in rows]


async def get_module_by_id(module_id: str) -> Optional[dict]:
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select id, module_key, name, slug, description, category, icon, route,
                   version, status, is_featured, sort_order, created_at, updated_at
            from nexa_modules where id = $1
            """,
            module_id,
        )
    return dict(row) if row else None
