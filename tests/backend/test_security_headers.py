"""
Тесты security headers middleware (аудит 22.08.2026, раздел 4:
CSP/Referrer-Policy/X-Content-Type-Options/frame policy).
"""
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_headers_present_on_successful_json_response():
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in resp.headers
    assert "Content-Security-Policy" in resp.headers


def test_headers_present_on_error_response():
    # 401 от get_current_user_id (нет Authorization) — проходит через
    # exception_handler, а не напрямую через роут. Заголовки должны быть
    # и здесь: middleware добавлен снаружи, оборачивает буквально ЛЮБОЙ
    # ответ, включая обработанные исключения.
    resp = client.get("/api/v1/admin/me")
    assert resp.status_code == 401
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in resp.headers


def test_headers_present_on_not_found_response():
    resp = client.get("/api/v1/this-route-does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_csp_forbids_scripts_and_allows_only_self_style():
    resp = client.get("/health")
    csp = resp.headers["Content-Security-Policy"]
    assert "script-src 'none'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_permissions_policy_blocks_unused_sensitive_apis():
    resp = client.get("/health")
    policy = resp.headers["Permissions-Policy"]
    assert "geolocation=()" in policy
    assert "camera=()" in policy
    assert "microphone=()" in policy


def test_hsts_has_reasonable_long_max_age_and_includes_subdomains():
    resp = client.get("/health")
    hsts = resp.headers["Strict-Transport-Security"]
    assert "includeSubDomains" in hsts
    # >= 1 год в секундах — общепринятый минимум для HSTS preload-листов
    assert "max-age=63072000" in hsts
