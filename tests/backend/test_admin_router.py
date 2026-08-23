"""
Тесты admin router через TestClient + dependency_overrides — без
живого Postgres, но с реальным FastAPI routing/permission-gating.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.admin.rbac import AdminContext, require_admin, get_admin_context_optional
from app.server import app

client = TestClient(app)

SUPPORT_ADMIN = AdminContext(
    user_id="user-1", admin_id="admin-1", role_key="support", role_name="Поддержка",
    permissions={"users.view", "documents.view"},
)
OWNER_ADMIN = AdminContext(
    user_id="user-owner", admin_id="admin-owner", role_key="owner", role_name="Владелец",
    permissions={"users.view", "users.block", "users.revoke_sessions", "audit.view"},
)


def _override_admin(ctx: AdminContext | None):
    """require_admin(permission) — фабрика зависимостей, для каждого
    permission создаётся СВОЙ callable-объект, поэтому override нужно
    ставить на каждый использованный в роутере permission-ключ
    отдельно (или патчить сам admin_repository — что и делаем ниже
    для эндпоинтов с разными правами в одном тесте)."""
    async def _dep(user_id: str = "user-1"):
        if ctx is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail={"error": {"code": "NOT_ADMIN", "message": "x"}})
        return ctx
    return _dep


def test_admin_me_returns_false_for_non_admin():
    app.dependency_overrides[get_admin_context_optional] = lambda: None
    try:
        resp = client.get("/api/v1/admin/me")
        assert resp.status_code == 200
        assert resp.json() == {"is_admin": False}
    finally:
        app.dependency_overrides.clear()


def test_admin_me_returns_role_and_permissions_for_admin():
    app.dependency_overrides[get_admin_context_optional] = lambda: SUPPORT_ADMIN
    try:
        resp = client.get("/api/v1/admin/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_admin"] is True
        assert body["role_key"] == "support"
        assert "users.view" in body["permissions"]
    finally:
        app.dependency_overrides.clear()


def test_admin_endpoints_require_authentication_at_all():
    # Без dependency_overrides — реальная цепочка get_current_user_id
    # должна отклонить запрос без токена, до того как дело дойдёт до RBAC.
    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401


def test_users_view_permission_required_for_dashboard():
    with patch(
        "app.admin.rbac.admin_repository.get_admin_context",
        new=AsyncMock(return_value={
            "admin_id": "a1", "role_key": "content_admin", "role_name": "Контент",
            "status": "active", "permissions": {"documents.view"},  # НЕТ users.view
        }),
    ):
        from app.auth.middleware import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: "user-1"
        try:
            resp = client.get("/api/v1/admin/dashboard")
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "PERMISSION_DENIED"
        finally:
            app.dependency_overrides.clear()


def test_block_user_requires_users_block_permission_not_just_view():
    with patch(
        "app.admin.rbac.admin_repository.get_admin_context",
        new=AsyncMock(return_value={
            "admin_id": "a1", "role_key": "support", "role_name": "Поддержка",
            "status": "active", "permissions": {"users.view"},  # НЕТ users.block
        }),
    ):
        from app.auth.middleware import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: "user-1"
        try:
            resp = client.post("/api/v1/admin/users/some-id/block", json={"reason": "spam"})
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


def test_block_user_with_permission_calls_repository_and_logs_audit():
    with patch("app.admin.rbac.admin_repository.get_admin_context", new=AsyncMock(return_value={
        "admin_id": "a1", "role_key": "security_admin", "role_name": "Безопасность",
        "status": "active", "permissions": {"users.block"},
    })), patch("app.routers.admin.repo.get_user", new=AsyncMock(side_effect=[
        {"id": "target-user", "is_blocked": False},  # before
    ])), patch("app.routers.admin.repo.set_user_blocked", new=AsyncMock(return_value={
        "id": "target-user", "is_blocked": True, "blocked_reason": "spam",
    })) as mock_set_blocked, patch("app.routers.admin.repo.log_admin_action", new=AsyncMock()) as mock_log:
        from app.auth.middleware import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: "user-1"
        try:
            resp = client.post("/api/v1/admin/users/target-user/block", json={"reason": "spam"})
            assert resp.status_code == 200
            assert resp.json()["is_blocked"] is True
            mock_set_blocked.assert_awaited_once_with("target-user", True, "spam")
            mock_log.assert_awaited_once()
            # action name зафиксирован — если кто-то переименует, тест это заметит
            assert mock_log.call_args.args[2] == "user.block"
        finally:
            app.dependency_overrides.clear()


def test_block_user_404_when_user_not_found_does_not_log_audit():
    with patch("app.admin.rbac.admin_repository.get_admin_context", new=AsyncMock(return_value={
        "admin_id": "a1", "role_key": "security_admin", "role_name": "Безопасность",
        "status": "active", "permissions": {"users.block"},
    })), patch("app.routers.admin.repo.get_user", new=AsyncMock(return_value=None)), \
         patch("app.routers.admin.repo.log_admin_action", new=AsyncMock()) as mock_log:
        from app.auth.middleware import get_current_user_id
        app.dependency_overrides[get_current_user_id] = lambda: "user-1"
        try:
            resp = client.post("/api/v1/admin/users/ghost/block", json={"reason": "x"})
            assert resp.status_code == 404
            mock_log.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()
