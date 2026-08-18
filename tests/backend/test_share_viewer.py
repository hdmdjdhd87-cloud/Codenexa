from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_shared_not_found_returns_html_not_json():
    # В тестовом окружении нет DATABASE_URL — это тоже честно проверяемый
    # случай: даже при недоступной БД пользователь не должен увидеть
    # сырой JSON, только понятную HTML-страницу (503, не JSON-ошибка).
    resp = client.get("/api/v1/aidocs/shared/nonexistent-token-xyz")
    assert resp.status_code in (404, 503)
    assert "text/html" in resp.headers["content-type"]
    assert not resp.text.strip().startswith("{")


def test_shared_page_has_no_json_content_type():
    resp = client.get("/api/v1/aidocs/shared/whatever-token")
    assert "application/json" not in resp.headers["content-type"]


def test_shared_download_invalid_format_rejected():
    resp = client.get("/api/v1/aidocs/shared/some-token/download/exe")
    assert resp.status_code == 400
    assert "text/html" in resp.headers["content-type"]


def test_shared_download_nonexistent_token():
    resp = client.get("/api/v1/aidocs/shared/nonexistent-token/download/pdf")
    assert resp.status_code in (404, 503)
    assert "text/html" in resp.headers["content-type"]


def test_shared_html_page_rendering_valid_document():
    from app.routers.aidocs import _shared_document_page
    from datetime import datetime

    doc = {
        "title": "Тестовый договор",
        "created_at": datetime(2026, 8, 20),
        "content_blocks": [
            {"type": "heading_center", "text": "ДОГОВОР"},
            {"type": "paragraph", "text": "Основной текст документа."},
            {"type": "signature_line", "text": "Иванов И.И."},
        ],
    }
    html = _shared_document_page(doc, "test-token-123")
    assert "Тестовый договор" in html
    assert "ДОГОВОР" in html
    assert "download/pdf" in html
    assert "download/docx" in html
    assert "<script" not in html  # публичная страница не должна тащить JS


def test_shared_html_page_escapes_user_content():
    from app.routers.aidocs import _shared_document_page
    from datetime import datetime

    doc = {
        "title": "<script>alert(1)</script>",
        "created_at": datetime(2026, 8, 20),
        "content_blocks": [{"type": "paragraph", "text": "<img src=x onerror=alert(1)>"}],
    }
    html = _shared_document_page(doc, "token")
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;script&gt;" in html


def test_shared_state_page_messages_are_distinct():
    from app.routers.aidocs import _shared_state_page

    expired = _shared_state_page("Срок действия ссылки истёк.")
    revoked = _shared_state_page("Ссылка была отозвана владельцем.")
    assert "истёк" in expired
    assert "отозвана" in revoked
    assert expired != revoked
