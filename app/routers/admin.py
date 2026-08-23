"""
Admin API (P0-10, аудит 22.08.2026) — минимальный, но реальный
бэкенд для будущей админ-панели (полноценный UI — P4, следующий шаг).

Каждый мутирующий эндпоинт: (1) проверяет конкретное permission через
require_admin(), (2) выполняет действие, (3) пишет в admin_audit_log —
именно в этом порядке, чтобы в аудит не попадали неудавшиеся попытки
(см. docstring admin_repository.log_admin_action).
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.admin.rbac import AdminContext, require_admin, get_admin_context_optional
from app.repositories import admin_repository as repo
from app.utils.errors import api_error
from fastapi import status

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _ip_hash(request: Request) -> str:
    """Никогда не пишем сырой IP в audit log (PII) — только необратимый
    хэш, достаточный, чтобы сопоставить "те же ли это запросы", но не
    восстановить исходный адрес."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


@router.get("/me")
async def admin_me(admin: AdminContext | None = Depends(get_admin_context_optional)) -> dict:
    """Не 403 для не-админа — фронтенду нужно тихо узнать 'я админ или нет',
    чтобы решить, показывать ли пункт меню админки."""
    if admin is None:
        return {"is_admin": False}
    return {
        "is_admin": True,
        "role_key": admin.role_key,
        "role_name": admin.role_name,
        "permissions": sorted(admin.permissions),
    }


@router.get("/dashboard")
async def dashboard(admin: AdminContext = Depends(require_admin("users.view"))) -> dict:
    return await repo.dashboard_counts()


@router.get("/users")
async def list_users(
    search: str | None = None,
    page: int = 1,
    admin: AdminContext = Depends(require_admin("users.view")),
) -> list[dict]:
    return await repo.list_users(search, page)


@router.get("/users/{user_id}")
async def get_user(user_id: str, admin: AdminContext = Depends(require_admin("users.view"))) -> dict:
    user = await repo.get_user(user_id)
    if not user:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")
    return user


class BlockUserRequest(BaseModel):
    reason: str


@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    payload: BlockUserRequest,
    request: Request,
    admin: AdminContext = Depends(require_admin("users.block")),
) -> dict:
    before = await repo.get_user(user_id)
    if not before:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")

    after = await repo.set_user_blocked(user_id, True, payload.reason)
    await repo.log_admin_action(
        admin.admin_id, admin.user_id, "user.block", "user", user_id, payload.reason,
        before={"is_blocked": before["is_blocked"]}, after={"is_blocked": True, "reason": payload.reason},
        ip_hash=_ip_hash(request),
    )
    return after


@router.post("/users/{user_id}/unblock")
async def unblock_user(
    user_id: str,
    request: Request,
    admin: AdminContext = Depends(require_admin("users.block")),
) -> dict:
    before = await repo.get_user(user_id)
    if not before:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")

    after = await repo.set_user_blocked(user_id, False, None)
    await repo.log_admin_action(
        admin.admin_id, admin.user_id, "user.unblock", "user", user_id, None,
        before={"is_blocked": before["is_blocked"]}, after={"is_blocked": False},
        ip_hash=_ip_hash(request),
    )
    return after


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_sessions(
    user_id: str,
    request: Request,
    admin: AdminContext = Depends(require_admin("users.revoke_sessions")),
) -> dict:
    result = await repo.revoke_user_sessions(user_id)
    if not result:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")
    await repo.log_admin_action(
        admin.admin_id, admin.user_id, "user.revoke_sessions", "user", user_id, None,
        ip_hash=_ip_hash(request),
    )
    return result


@router.get("/audit-log")
async def audit_log(page: int = 1, admin: AdminContext = Depends(require_admin("audit.view"))) -> list[dict]:
    return await repo.list_audit_log(page)
