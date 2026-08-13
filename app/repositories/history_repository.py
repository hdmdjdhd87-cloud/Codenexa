from __future__ import annotations

import json

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status

PAGE_SIZE = 20


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def list_history(user_id: str, page: int = 1) -> list[dict]:
    pool = await _pool_or_503()
    offset = max(0, (page - 1)) * PAGE_SIZE
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select h.id, h.action, h.metadata, h.created_at,
                   h.module_id, m.name as module_name
            from nexa_history h
            left join nexa_modules m on m.id = h.module_id
            where h.user_id = $1
            order by h.created_at desc
            limit $2 offset $3
            """,
            user_id,
            PAGE_SIZE,
            offset,
        )
    return [dict(r) for r in rows]


async def add_history_event(user_id: str, action: str, module_id: str | None = None, metadata: dict | None = None) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_history (user_id, module_id, action, metadata)
            values ($1, $2, $3, $4::jsonb)
            returning id, module_id, action, metadata, created_at
            """,
            user_id,
            module_id,
            action,
            json.dumps(metadata or {}),
        )
    return dict(row)
