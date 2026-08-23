"""
require_admin(permission) — dependency factory для admin-эндпоинтов
(P0-10, аудит 22.08.2026).

Строится ПОВЕРХ get_current_user_id (обычная user-сессия), не заменяет
её — админ сначала обычный авторизованный пользователь, и уже для него
дополнительно проверяется admin_users/admin_role_permissions. Это и
есть "не хардкодить admin ID в if" — вместо этого явная зависимость,
которую видно в сигнатуре каждого защищённого роута.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.auth.middleware import get_current_user_id
from app.repositories import admin_repository


class AdminContext:
    __slots__ = ("user_id", "admin_id", "role_key", "role_name", "permissions")

    def __init__(self, user_id: str, admin_id: str, role_key: str, role_name: str, permissions: set[str]):
        self.user_id = user_id
        self.admin_id = admin_id
        self.role_key = role_key
        self.role_name = role_name
        self.permissions = permissions


def require_admin(permission: str) -> Callable:
    """Возвращает FastAPI-зависимость, требующую конкретное permission.
    Использование: `admin: AdminContext = Depends(require_admin("users.block"))`.
    """

    async def _dependency(user_id: str = Depends(get_current_user_id)) -> AdminContext:
        ctx = await admin_repository.get_admin_context(user_id)
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "NOT_ADMIN", "message": "Требуются права администратора."}},
            )
        if permission not in ctx["permissions"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": f"Недостаточно прав: требуется '{permission}'.",
                    }
                },
            )
        return AdminContext(
            user_id=user_id,
            admin_id=ctx["admin_id"],
            role_key=ctx["role_key"],
            role_name=ctx["role_name"],
            permissions=ctx["permissions"],
        )

    return _dependency


async def get_admin_context_optional(user_id: str = Depends(get_current_user_id)) -> AdminContext | None:
    """Для эндпоинтов вроде GET /admin/me — не 403, а просто null для не-админа
    (фронтенду нужно узнать 'это админ или нет', а не получить ошибку)."""
    ctx = await admin_repository.get_admin_context(user_id)
    if ctx is None:
        return None
    return AdminContext(
        user_id=user_id,
        admin_id=ctx["admin_id"],
        role_key=ctx["role_key"],
        role_name=ctx["role_name"],
        permissions=ctx["permissions"],
    )
