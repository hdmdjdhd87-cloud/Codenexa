from app.middleware.rate_limit_tiers import resolve_tier


def test_healthcheck_paths_are_exempt():
    assert resolve_tier("GET", "/health") is None
    assert resolve_tier("GET", "/ready") is None


def test_auth_endpoint_uses_ip_only_strict_tier():
    tier = resolve_tier("POST", "/api/v1/auth/telegram")
    assert tier is not None
    assert tier.scope == "auth"
    assert tier.identity_kind == "ip_only"
    assert tier.limit == 20


def test_ocr_endpoint_uses_ocr_tier():
    tier = resolve_tier("POST", "/api/v1/aidocs/ocr")
    assert tier.scope == "ocr"


def test_document_import_uses_ocr_tier_too():
    # тяжёлая CPU-операция (парсинг docx/pdf), тот же лимит, что и OCR
    tier = resolve_tier("POST", "/api/v1/aidocs/documents/import")
    assert tier.scope == "ocr"


def test_export_docx_uses_export_tier_not_generic_read():
    tier = resolve_tier("GET", "/api/v1/aidocs/documents/abc-123/export/docx")
    assert tier.scope == "export"


def test_export_pdf_uses_export_tier():
    tier = resolve_tier("GET", "/api/v1/aidocs/documents/abc-123/export/pdf")
    assert tier.scope == "export"


def test_get_single_document_is_read_tier_not_export():
    # Регрессия: GET /documents/{id} НЕ должен случайно попасть в export
    # только потому что оба пути начинаются с /documents/{id}
    tier = resolve_tier("GET", "/api/v1/aidocs/documents/abc-123")
    assert tier.scope == "read"


def test_get_versions_is_read_tier():
    tier = resolve_tier("GET", "/api/v1/aidocs/documents/abc-123/versions")
    assert tier.scope == "read"


def test_public_share_view_uses_ip_only_tier():
    tier = resolve_tier("GET", "/api/v1/aidocs/shared/some-token")
    assert tier.scope == "public_share"
    assert tier.identity_kind == "ip_only"


def test_public_share_download_uses_public_share_tier_not_export():
    # /download/ в пути публичной ссылки — не должен путаться с
    # авторизованным /export/ через contains-matching
    tier = resolve_tier("GET", "/api/v1/aidocs/shared/some-token/download/pdf")
    assert tier.scope == "public_share"


def test_create_document_post_uses_mutation_tier():
    tier = resolve_tier("POST", "/api/v1/aidocs/documents")
    assert tier.scope == "mutation"


def test_restore_version_post_uses_mutation_tier():
    tier = resolve_tier("POST", "/api/v1/aidocs/documents/abc/versions/xyz/restore")
    assert tier.scope == "mutation"


def test_list_documents_get_uses_read_tier():
    tier = resolve_tier("GET", "/api/v1/aidocs/documents")
    assert tier.scope == "read"


def test_templates_get_uses_read_tier():
    tier = resolve_tier("GET", "/api/v1/aidocs/templates")
    assert tier.scope == "read"


def test_unrelated_api_path_falls_back_to_general_tier():
    tier = resolve_tier("GET", "/api/v1/users/me")
    assert tier.scope == "general"


def test_path_outside_api_is_not_limited():
    assert resolve_tier("GET", "/some/random/path") is None


def test_delete_document_uses_mutation_tier():
    tier = resolve_tier("DELETE", "/api/v1/aidocs/documents/abc-123")
    assert tier.scope == "mutation"


def test_patch_rename_uses_mutation_tier():
    tier = resolve_tier("PATCH", "/api/v1/aidocs/documents/abc-123/rename")
    assert tier.scope == "mutation"
