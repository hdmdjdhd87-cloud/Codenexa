from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_without_db_returns_degraded():
    # В тестовом окружении DATABASE_URL не задан — /ready должен не падать,
    # а явно сообщить о degraded-состоянии, а не 500.
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] is False
    assert body["status"] == "degraded"
