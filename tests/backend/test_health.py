from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_without_db_returns_503_degraded():
    # В тестовом окружении DATABASE_URL не задан — /ready должен явно
    # сигнализировать сбой через HTTP-код (503), а не только в теле
    # JSON. Healthcheck-механизмы (в т.ч. Railway, см. railway.json
    # healthcheckPath) обычно проверяют именно HTTP-статус — 200 при
    # реальном сбое БД сделал бы весь смысл healthcheckPath=/ready
    # чисто косметическим (F-011 из аудита 22.08.2026).
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["database"] is False
    assert body["status"] == "degraded"


def test_ready_with_healthy_db_returns_200_ok():
    with patch("app.routers.health.ping", new=AsyncMock(return_value=True)):
        resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] is True
    assert body["status"] == "ok"
