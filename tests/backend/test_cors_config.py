from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_cors_preflight_allows_only_used_methods():
    # F-014: было allow_methods=["*"] — сужено до реально используемого
    # набора. Preflight должен вернуть именно этот список, не "*".
    resp = client.options(
        "/api/v1/aidocs/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    allowed = resp.headers.get("access-control-allow-methods", "")
    assert "POST" in allowed
    assert allowed != "*"


def test_cors_preflight_allows_idempotency_key_header():
    # Idempotency-Key реально используется фронтендом (п.7) — должен
    # быть в allow_headers, иначе браузер заблокирует запросы с ним.
    resp = client.options(
        "/api/v1/aidocs/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key",
        },
    )
    allowed_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "idempotency-key" in allowed_headers


def test_cors_preflight_does_not_wildcard_methods():
    resp = client.options(
        "/api/v1/aidocs/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-methods") != "*"
