"""
Тесты require_admin / get_admin_context_optional (P0-10, аудит).
Репозиторий мокается — тестируем именно логику разрешения прав,
не SQL.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.admin.rbac import require_admin, get_admin_context_optional


OWNER_CTX = {
    "admin_id": "admin-1",
    "role_key": "owner",
    "role_name": "Владелец",
    "status": "active",
    "permissions": {"users.view", "users.block", "audit.view"},
}

SUPPORT_CTX = {
    "admin_id": "admin-2",
    "role_key": "support",
    "role_name": "Поддержка",
    "status": "active",
    "permissions": {"users.view", "documents.view"},
}


@pytest.mark.asyncio
async def test_non_admin_user_rejected_with_403_not_admin():
    dependency = require_admin("users.view")
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await dependency(user_id="plain-user")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "NOT_ADMIN"


@pytest.mark.asyncio
async def test_admin_with_required_permission_passes():
    dependency = require_admin("users.view")
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=SUPPORT_CTX):
        ctx = await dependency(user_id="user-support")
    assert ctx.role_key == "support"
    assert ctx.admin_id == "admin-2"


@pytest.mark.asyncio
async def test_admin_without_required_permission_rejected_403():
    # support имеет users.view, но НЕ users.block
    dependency = require_admin("users.block")
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=SUPPORT_CTX):
        with pytest.raises(HTTPException) as exc_info:
            await dependency(user_id="user-support")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_owner_has_any_permission():
    dependency = require_admin("audit.view")
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=OWNER_CTX):
        ctx = await dependency(user_id="user-owner")
    assert ctx.role_key == "owner"


@pytest.mark.asyncio
async def test_get_admin_context_optional_returns_none_for_non_admin():
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=None):
        ctx = await get_admin_context_optional(user_id="plain-user")
    assert ctx is None


@pytest.mark.asyncio
async def test_get_admin_context_optional_returns_context_for_admin():
    with patch("app.admin.rbac.admin_repository.get_admin_context", return_value=SUPPORT_CTX):
        ctx = await get_admin_context_optional(user_id="user-support")
    assert ctx is not None
    assert ctx.role_key == "support"
    assert "users.view" in ctx.permissions
