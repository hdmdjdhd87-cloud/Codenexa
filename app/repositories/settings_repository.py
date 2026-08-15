from __future__ import annotations

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def get_settings_for_user(user_id: str) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_settings (user_id)
            values ($1)
            on conflict (user_id) do update set user_id = excluded.user_id
            returning id, user_id, language, theme, haptic_feedback, notifications_enabled, settings_json
            """,
            user_id,
        )
    return dict(row)


async def update_settings_for_user(user_id: str, patch: dict) -> dict:
    pool = await _pool_or_503()
    fields = []
    values: list = []
    idx = 1
    allowed = {"language", "theme", "haptic_feedback", "notifications_enabled"}
    for key, value in patch.items():
        if key not in allowed or value is None:
            continue
        idx += 1
        fields.append(f"{key} = ${idx}")
        values.append(value)
    if not fields:
        return await get_settings_for_user(user_id)

    query = f"""
        update nexa_settings set {', '.join(fields)}
        where user_id = $1
        returning id, user_id, language, theme, haptic_feedback, notifications_enabled, settings_json
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, user_id, *values)
    if row is None:
        return await get_settings_for_user(user_id)
    return dict(row)
