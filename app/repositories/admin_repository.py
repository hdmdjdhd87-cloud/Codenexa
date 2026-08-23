"""
Admin RBAC repository (P0-10, аудит 22.08.2026).

Роли/права хранятся в БД (admin_roles/admin_permissions/
admin_role_permissions, см. migrations/0011), не хардкодятся в
Python — можно менять матрицу прав без деплоя.

owner получает ВСЕ существующие permission-ключи автоматически на
уровне этого кода (не через отдельные строки в admin_role_permissions
для owner) — это одна намеренная асимметрия: owner не может
"забыть" выдать себе новое право, когда оно появляется в системе.
"""
from __future__ import annotations

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def get_admin_context(user_id: str) -> dict | None:
    """Возвращает {admin_id, role_key, role_name, status, permissions: set[str]}
    для активного админа, или None если пользователь не админ / suspended.
    """
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        admin_row = await conn.fetchrow(
            """
            select au.id as admin_id, au.status, r.key as role_key, r.name as role_name
            from admin_users au
            join admin_roles r on r.id = au.role_id
            where au.user_id = $1
            """,
            user_id,
        )
        if not admin_row or admin_row["status"] != "active":
            return None

        if admin_row["role_key"] == "owner":
            perm_rows = await conn.fetch("select key from admin_permissions")
        else:
            perm_rows = await conn.fetch(
                """
                select p.key
                from admin_role_permissions rp
                join admin_permissions p on p.id = rp.permission_id
                join admin_users au on au.role_id = rp.role_id
                where au.user_id = $1
                """,
                user_id,
            )

    return {
        "admin_id": str(admin_row["admin_id"]),
        "role_key": admin_row["role_key"],
        "role_name": admin_row["role_name"],
        "status": admin_row["status"],
        "permissions": {r["key"] for r in perm_rows},
    }


async def log_admin_action(
    actor_admin_id: str,
    actor_user_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    reason: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip_hash: str | None = None,
) -> None:
    """Append-only запись в admin_audit_log. Вызывается ПОСЛЕ успешного
    действия — если действие упало, лог не пишем (нет смысла аудировать
    несостоявшееся изменение отдельной строкой "attempted")."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            insert into admin_audit_log
                (actor_admin_id, actor_user_id, action, target_type, target_id, reason, before_json, after_json, ip_hash)
            values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9)
            """,
            actor_admin_id,
            actor_user_id,
            action,
            target_type,
            target_id,
            reason,
            before or {},
            after or {},
            ip_hash,
        )


async def list_audit_log(page: int = 1, page_size: int = 50) -> list[dict]:
    pool = await _pool_or_503()
    offset = max(0, page - 1) * page_size
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select al.id, al.action, al.target_type, al.target_id, al.reason,
                   al.before_json, al.after_json, al.created_at,
                   u.username as actor_username, u.telegram_user_id as actor_telegram_id
            from admin_audit_log al
            left join admin_users au on au.id = al.actor_admin_id
            left join nexa_users u on u.id = au.user_id
            order by al.created_at desc
            limit $1 offset $2
            """,
            page_size,
            offset,
        )
    return [dict(r) for r in rows]


async def list_users(search: str | None, page: int = 1, page_size: int = 30) -> list[dict]:
    pool = await _pool_or_503()
    offset = max(0, page - 1) * page_size
    async with pool.acquire() as conn:
        if search:
            rows = await conn.fetch(
                """
                select id, telegram_user_id, username, first_name, last_name,
                       is_blocked, blocked_reason, created_at, last_seen_at
                from nexa_users
                where username ilike $1 or first_name ilike $1 or last_name ilike $1
                   or telegram_user_id::text = $2
                order by created_at desc
                limit $3 offset $4
                """,
                f"%{search}%",
                search,
                page_size,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                select id, telegram_user_id, username, first_name, last_name,
                       is_blocked, blocked_reason, created_at, last_seen_at
                from nexa_users
                order by created_at desc
                limit $1 offset $2
                """,
                page_size,
                offset,
            )
    return [dict(r) for r in rows]


async def get_user(user_id: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select id, telegram_user_id, username, first_name, last_name,
                   is_blocked, blocked_at, blocked_reason, created_at, last_seen_at
            from nexa_users where id = $1
            """,
            user_id,
        )
    return dict(row) if row else None


async def set_user_blocked(user_id: str, blocked: bool, reason: str | None) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            update nexa_users
            set is_blocked = $2,
                blocked_at = case when $2 then now() else null end,
                blocked_reason = case when $2 then $3 else null end
            where id = $1
            returning id, telegram_user_id, username, is_blocked, blocked_at, blocked_reason
            """,
            user_id,
            blocked,
            reason,
        )
    return dict(row) if row else None


async def revoke_user_sessions(user_id: str) -> dict | None:
    """sessions_valid_from = now() — все уже выданные токены с iat раньше
    этого момента перестают приниматься в get_current_user_id (см.
    app/auth/middleware.py). Не блокирует пользователя навсегда: следующий
    Telegram-логин выдаёт свежий токен."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "update nexa_users set sessions_valid_from = now() where id = $1 returning id, sessions_valid_from",
            user_id,
        )
    return dict(row) if row else None


async def dashboard_counts() -> dict:
    """Минимальный, но реальный dashboard (не выдуманные метрики) —
    полноценные p50/p95/p99/observability из аудита (P1) сюда
    сознательно не включены: там нужен отдельный telemetry stack,
    а не SQL count(*)."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select
                (select count(*) from nexa_users) as total_users,
                (select count(*) from nexa_users where is_blocked) as blocked_users,
                (select count(*) from nexa_docs_documents) as total_documents,
                (select count(*) from nexa_docs_shares where revoked_at is null and (expires_at is null or expires_at > now())) as active_shares,
                (select count(*) from nexa_rate_limit_hits where window_start > now() - interval '1 hour') as rate_limit_windows_last_hour
            """
        )
    return dict(row)
