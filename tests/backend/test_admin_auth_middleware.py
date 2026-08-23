"""
Тесты на новую проверку is_blocked/sessions_valid_from в
get_current_user_id (P0-10, admin RBAC, аудит 22.08.2026).

БД мокается (FakePool/FakeConn) — реального Postgres в песочнице нет,
но сама логика (что делает middleware с результатом запроса) полностью
тестируема изолированно.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.auth.middleware import get_current_user_id
from app.auth.session import create_session_token
from app.config import get_settings

TEST_JWT_SECRET = "test-secret-for-admin-auth-tests"


@pytest.fixture(autouse=True)
def jwt_secret_configured(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeConn:
    def __init__(self, row):
        self._row = row

    async def fetchrow(self, query, *args):
        return self._row


class FakePool:
    def __init__(self, row):
        self._row = row

    def acquire(self):
        return _FakeAcquireCtx(self._row)


class _FakeAcquireCtx:
    def __init__(self, row):
        self._row = row

    async def __aenter__(self):
        return FakeConn(self._row)

    async def __aexit__(self, *exc):
        return False


def _bearer(user_id: str) -> str:
    token = create_session_token(user_id)
    return f"Bearer {token}"


# ---------- missing/garbage auth (unaffected by DB check — fail before it) ----------

@pytest.mark.asyncio
async def test_missing_authorization_header_rejected_without_db():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(authorization=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_garbage_token_rejected_without_db():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_id(authorization="Bearer not-a-real-jwt")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "SESSION_INVALID"


# ---------- DB-aware checks ----------

@pytest.mark.asyncio
async def test_valid_token_and_active_user_passes():
    row = {"is_blocked": False, "valid_from_ts": 0}  # sessions_valid_from в далёком прошлом — токен всегда свежее
    with patch("app.auth.middleware.get_pool", return_value=FakePool(row)):
        user_id = await get_current_user_id(authorization=_bearer("user-123"))
    assert user_id == "user-123"


@pytest.mark.asyncio
async def test_blocked_user_rejected_with_403():
    row = {"is_blocked": True, "valid_from_ts": 0}
    with patch("app.auth.middleware.get_pool", return_value=FakePool(row)):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(authorization=_bearer("user-123"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"]["code"] == "ACCOUNT_BLOCKED"


@pytest.mark.asyncio
async def test_revoked_session_rejected_with_401():
    # sessions_valid_from далеко в будущем -> любой уже выпущенный токен считается старым
    row = {"is_blocked": False, "valid_from_ts": int(time.time()) + 3600}
    with patch("app.auth.middleware.get_pool", return_value=FakePool(row)):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(authorization=_bearer("user-123"))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_user_not_found_in_db_rejected():
    with patch("app.auth.middleware.get_pool", return_value=FakePool(None)):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(authorization=_bearer("deleted-user"))
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error"]["code"] == "SESSION_INVALID"


@pytest.mark.asyncio
async def test_database_unavailable_fails_closed_503():
    # Security-проверка — fail-CLOSED (в отличие от rate limiting, которое fail-open)
    with patch("app.auth.middleware.get_pool", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id(authorization=_bearer("user-123"))
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"]["code"] == "DATABASE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_token_issued_at_or_after_valid_from_boundary_is_accepted():
    # issued_at >= valid_from_ts (не строго >) — граница включительно на
    # стороне "разрешено": захватываем valid_from ДО создания токена, так
    # что реальный iat токена гарантированно >= valid_from_ts.
    valid_from_ts = int(time.time())
    token_header = _bearer("user-123")
    row = {"is_blocked": False, "valid_from_ts": valid_from_ts}
    with patch("app.auth.middleware.get_pool", return_value=FakePool(row)):
        user_id = await get_current_user_id(authorization=token_header)
    assert user_id == "user-123"
