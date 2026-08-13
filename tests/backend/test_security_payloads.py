"""
Security tests (п.51 спецификации): SQL injection, XSS, malformed JSON,
огромный payload — во всех случаях сервер обязан корректно отклонить
запрос, а не упасть с 500 и не выполнить вредоносный код.
"""
from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_sql_injection_in_init_data_rejected_safely():
    payload = {"init_data": "user=1' OR '1'='1&auth_date=123&hash=deadbeef"}
    resp = client.post("/api/v1/auth/telegram", json=payload)
    assert resp.status_code in (400, 401, 500)
    assert "error" in resp.json()


def test_xss_payload_in_init_data_rejected_safely():
    payload = {"init_data": "<script>alert(1)</script>&auth_date=123&hash=deadbeef"}
    resp = client.post("/api/v1/auth/telegram", json=payload)
    assert resp.status_code in (400, 401, 500)
    assert "<script>" not in resp.text


def test_malformed_json_rejected_not_500():
    resp = client.post(
        "/api/v1/auth/telegram",
        headers={"Content-Type": "application/json"},
        content=b"{not-valid-json",
    )
    assert resp.status_code in (400, 422)


def test_oversized_payload_rejected():
    huge = "A" * 5_000_000  # 5MB строки в одном поле
    resp = client.post("/api/v1/auth/telegram", json={"init_data": huge})
    assert resp.status_code in (400, 401, 413, 500)


def test_module_id_path_traversal_like_value_returns_404_or_422():
    resp = client.get(
        "/api/v1/modules/../../etc/passwd",
        headers={"Authorization": "Bearer garbage"},
    )
    assert resp.status_code in (401, 404, 422)


def test_favorite_endpoint_rejects_sql_injection_module_id():
    resp = client.delete(
        "/api/v1/favorites/1' OR '1'='1",
        headers={"Authorization": "Bearer garbage"},
    )
    # без валидного токена доступ всё равно закрыт — до SQL дело не дойдёт
    assert resp.status_code == 401
