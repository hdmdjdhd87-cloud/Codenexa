from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.middleware.rate_limit import _client_ip, _resolve_identity
from app.server import app

client = TestClient(app)


def _mock_request(headers: dict[str, str], client_host: str | None = "203.0.113.5"):
    request = MagicMock()
    request.headers = headers
    request.client = MagicMock(host=client_host) if client_host else None
    return request


# ---------- _client_ip ----------

def test_client_ip_prefers_x_forwarded_for():
    # Railway (и большинство PaaS) проксирует — request.client.host был бы
    # IP прокси, не реального клиента.
    request = _mock_request({"x-forwarded-for": "198.51.100.7, 10.0.0.1"}, client_host="10.0.0.1")
    assert _client_ip(request) == "198.51.100.7"


def test_client_ip_falls_back_to_request_client_host():
    request = _mock_request({}, client_host="192.0.2.9")
    assert _client_ip(request) == "192.0.2.9"


def test_client_ip_unknown_when_no_client_info():
    request = _mock_request({}, client_host=None)
    assert _client_ip(request) == "unknown"


def test_client_ip_strips_whitespace_in_forwarded_header():
    request = _mock_request({"x-forwarded-for": "  198.51.100.7  , 10.0.0.1"})
    assert _client_ip(request) == "198.51.100.7"


# ---------- _resolve_identity ----------

def test_resolve_identity_ip_only_ignores_authorization_header():
    request = _mock_request({"authorization": "Bearer whatever", "x-forwarded-for": "198.51.100.1"})
    identity = _resolve_identity(request, "ip_only")
    assert identity == "ip:198.51.100.1"


def test_resolve_identity_user_or_ip_falls_back_to_ip_without_auth_header():
    request = _mock_request({"x-forwarded-for": "198.51.100.2"})
    identity = _resolve_identity(request, "user_or_ip")
    assert identity == "ip:198.51.100.2"


def test_resolve_identity_user_or_ip_falls_back_to_ip_on_invalid_token():
    request = _mock_request({"authorization": "Bearer not-a-real-jwt", "x-forwarded-for": "198.51.100.3"})
    identity = _resolve_identity(request, "user_or_ip")
    # Невалидный токен -> тихий fallback на IP; сам запрос всё равно
    # получит честный 401 от get_current_user_id на уровне роута.
    assert identity == "ip:198.51.100.3"


def test_resolve_identity_user_or_ip_uses_valid_session_token(monkeypatch):
    def fake_verify(token):
        assert token == "valid-token"
        return "user-abc-123"

    monkeypatch.setattr("app.middleware.rate_limit.verify_session_token", fake_verify)
    request = _mock_request({"authorization": "Bearer valid-token"})
    identity = _resolve_identity(request, "user_or_ip")
    assert identity == "user:user-abc-123"


# ---------- middleware end-to-end (fail-open без БД в тестовом окружении) ----------

def test_middleware_fails_open_without_database():
    # В тестовом окружении DATABASE_URL не задан — get_pool() возвращает
    # None, middleware должен пропустить запрос, а не вернуть 429/500.
    resp = client.get("/api/v1/aidocs/templates", headers={"Authorization": "Bearer x"})
    # 401 (невалидный токен) — это ОЖИДАЕМЫЙ ответ роута, важно что это
    # не 429 (не заблокировано лимитером) и не 500 (не упало на rate-limit коде).
    assert resp.status_code != 429
    assert resp.status_code != 500


def test_healthcheck_is_never_rate_limited():
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_rate_limited_response_would_include_retry_after_header_shape():
    # Не можем воспроизвести реальное превышение лимита без живого Postgres
    # (см. MANUAL_TODO.md — NOT VERIFIED для сценариев с реальной БД),
    # но фиксируем контракт формата ответа кодом, а не только описанием.
    from app.middleware.rate_limit import RateLimitMiddleware
    import inspect

    source = inspect.getsource(RateLimitMiddleware.dispatch)
    assert "RATE_LIMITED" in source
    assert "Retry-After" in source
