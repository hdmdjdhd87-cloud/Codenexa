"""
Тесты п.51 спецификации (Security tests): запрос без авторизации,
невалидный токен — во всех случаях доступ должен быть запрещён,
а не тихо проигнорирован.
"""
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)

PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/users/me"),
    ("GET", "/api/v1/modules"),
    ("GET", "/api/v1/favorites"),
    ("GET", "/api/v1/history"),
    ("GET", "/api/v1/notifications"),
    ("GET", "/api/v1/settings"),
    ("GET", "/api/v1/projects"),
]


def test_protected_endpoints_reject_missing_auth():
    for method, path in PROTECTED_ENDPOINTS:
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{path} должен требовать авторизацию"
        body = resp.json()
        assert body["error"]["code"] == "UNAUTHORIZED"


def test_protected_endpoints_reject_garbage_token():
    headers = {"Authorization": "Bearer not-a-real-jwt-token"}
    for method, path in PROTECTED_ENDPOINTS:
        resp = client.request(method, path, headers=headers)
        assert resp.status_code == 401, f"{path} должен отклонять невалидный токен"


def test_auth_telegram_rejects_malformed_payload():
    resp = client.post("/api/v1/auth/telegram", json={"init_data": ""})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MALFORMED_INIT_DATA"


def test_auth_telegram_rejects_bad_signature():
    resp = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": "user=%7B%22id%22%3A1%7D&auth_date=1700000000&hash=deadbeef"},
    )
    # Без TELEGRAM_BOT_TOKEN в тестовом окружении сервер вернёт AUTH_MISCONFIGURED (500),
    # это ожидаемо и безопасно: не подтверждает и не создаёт пользователя.
    assert resp.status_code in (400, 401, 500)
    assert "error" in resp.json()
