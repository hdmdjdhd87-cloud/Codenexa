from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.auth.middleware import get_current_user_id
from app.repositories import aidocs_repository as repo
from app.repositories.history_repository import add_history_event
from app.repositories.idempotency import with_idempotency, compute_request_hash
from app.document_engine.template_fill import fill_template, validate_required_fields
from app.document_engine.docx_renderer import render_docx
from app.document_engine.pdf_renderer import render_pdf
from app.document_engine.qa import DocumentQAError, check_docx, check_pdf
from app.document_engine.ocr import OcrError, extract_text_from_image
from app.document_engine.import_reader import (
    ImportError_,
    extract_text_from_docx_file,
    extract_text_from_pdf_file,
)
from app.ai.provider import ai_is_configured
from app.repositories import conversation_repository as conv_repo
from app.document_intelligence.agent import DocumentAgent, ConversationState
from app.document_intelligence.analyzer import analyze_document
from app.document_intelligence.ocr_autofill import suggest_field_values
from app.document_engine.version_diff import diff_content_blocks, diff_result_to_dict
from app.utils.errors import api_error
from fastapi import status

router = APIRouter(prefix="/api/v1/aidocs", tags=["aidocs"])
public_router = APIRouter(prefix="/api/v1/aidocs/shared", tags=["aidocs-public"])


@router.get("/status")
async def ai_status() -> dict:
    """Фронтенд использует это, чтобы честно показать, доступен ли AI-диалог,
    не пытаясь угадывать по ошибкам отдельных запросов."""
    return {"ai_available": ai_is_configured()}


@router.get("/templates")
async def get_templates(_user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await repo.list_templates()


class CreateDocumentRequest(BaseModel):
    template_id: str
    title: str
    field_values: dict[str, str]


@router.post("/documents")
async def create_document(
    payload: CreateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    template = await repo.get_template(payload.template_id)
    if not template:
        raise api_error(status.HTTP_404_NOT_FOUND, "TEMPLATE_NOT_FOUND", "Шаблон не найден.")

    missing = validate_required_fields(template["fields_schema"], payload.field_values)
    if missing:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "MISSING_REQUIRED_FIELDS",
            f"Не заполнены обязательные поля: {', '.join(missing)}.",
        )

    async def _work() -> dict:
        content_blocks = fill_template(template["body_template"], payload.field_values)
        doc = await repo.create_document(
            user_id, template["id"], payload.title, template["category"], payload.field_values, content_blocks
        )
        await add_history_event(
            user_id, "document_create", metadata={"document_id": str(doc["id"]), "title": doc["title"]}
        )
        return doc

    # Идемпотентность (п.7 промпта): двойной клик "Создать документ" с
    # тем же Idempotency-Key вернёт УЖЕ созданный документ, а не создаст
    # второй дубликат. request_hash защищает от обратного случая — если
    # клиент по ошибке переиспользует ключ для ДРУГОГО документа/полей,
    # это 422, а не тихая подмена результата (найдено при повторной
    # проверке аудита: document_id/version_id часто приходят из URL, а
    # не из тела, и не входили в защиту раньше).
    request_hash = compute_request_hash(payload.template_id, payload.title, payload.field_values)
    return await with_idempotency(user_id, "create_document", idempotency_key, _work, request_hash=request_hash)


@router.get("/documents")
async def get_documents(
    search: str | None = Query(default=None), user_id: str = Depends(get_current_user_id)
) -> list[dict]:
    return await repo.list_documents(user_id, search=search)


@router.get("/documents/{document_id}")
async def get_document(document_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    doc = await repo.get_document(user_id, document_id)
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    return doc


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    deleted = await repo.delete_document(user_id, document_id)
    if not deleted:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    await add_history_event(user_id, "document_delete", metadata={"document_id": document_id})
    return {"status": "ok"}


class FavoriteRequest(BaseModel):
    is_favorite: bool


@router.patch("/documents/{document_id}/favorite")
async def set_favorite(document_id: str, payload: FavoriteRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    doc = await repo.toggle_favorite(user_id, document_id, payload.is_favorite)
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    return doc


@router.get("/documents/{document_id}/versions")
async def get_versions(document_id: str, user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await repo.list_versions(user_id, document_id)


@router.post("/documents/{document_id}/versions/{version_id}/restore")
async def restore_version(
    document_id: str,
    version_id: str,
    user_id: str = Depends(get_current_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """
    Восстановление версии (п.2 промпта). Создаёт НОВУЮ версию поверх
    существующей истории (не удаляет и не переписывает старые версии) —
    см. docstring repo.restore_version.
    """

    async def _work() -> dict:
        result = await repo.restore_version(user_id, document_id, version_id)
        if not result:
            raise api_error(status.HTTP_404_NOT_FOUND, "VERSION_NOT_FOUND", "Версия или документ не найдены.")
        await add_history_event(
            user_id,
            "document_version_restore",
            metadata={"document_id": document_id, "restored_from_version_id": version_id},
        )
        return {"document": result["document"], "version": result["version"]}

    # Идемпотентность (п.7 промпта): двойной клик "Восстановить" с тем
    # же Idempotency-Key не создаст две одинаковые restored-версии подряд.
    # request_hash включает document_id+version_id (пришедшие из URL) —
    # переиспользование того же ключа для ДРУГОЙ версии/документа даёт
    # 422, а не результат первого запроса.
    request_hash = compute_request_hash(document_id, version_id)
    return await with_idempotency(user_id, "restore_version", idempotency_key, _work, request_hash=request_hash)


@router.get("/documents/{document_id}/versions/compare")
async def compare_versions(
    document_id: str,
    from_version_id: str = Query(..., alias="from"),
    to_version_id: str = Query(..., alias="to"),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Structural diff между двумя версиями (п.3 промпта) — added/removed/changed
    по content_blocks, без внешних AI/LLM: SequenceMatcher над блоками + word-level
    diff внутри изменённых блоков (app/document_engine/version_diff.py)."""
    versions = await repo.get_two_versions(user_id, document_id, from_version_id, to_version_id)
    if not versions:
        raise api_error(status.HTTP_404_NOT_FOUND, "VERSION_NOT_FOUND", "Одна из версий или документ не найдены.")

    diff = diff_content_blocks(versions["a"]["content_blocks"], versions["b"]["content_blocks"])
    return {
        "from": {"version_number": versions["a"]["version_number"], "created_at": versions["a"]["created_at"]},
        "to": {"version_number": versions["b"]["version_number"], "created_at": versions["b"]["created_at"]},
        "diff": diff_result_to_dict(diff),
    }


@router.get("/documents/{document_id}/export/docx")
async def export_docx(document_id: str, user_id: str = Depends(get_current_user_id)) -> Response:
    doc = await repo.get_document(user_id, document_id)
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    data = render_docx(doc["title"], doc["content_blocks"])
    try:
        check_docx(data)
    except DocumentQAError as exc:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "EXPORT_QA_FAILED", str(exc)) from exc
    await add_history_event(user_id, "document_export_docx", metadata={"document_id": document_id})
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(doc["title"])}.docx"'},
    )


@router.get("/documents/{document_id}/export/pdf")
async def export_pdf(document_id: str, user_id: str = Depends(get_current_user_id)) -> Response:
    doc = await repo.get_document(user_id, document_id)
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    data = render_pdf(doc["title"], doc["content_blocks"])
    try:
        check_pdf(data)
    except DocumentQAError as exc:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "EXPORT_QA_FAILED", str(exc)) from exc
    await add_history_event(user_id, "document_export_pdf", metadata={"document_id": document_id})
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(doc["title"])}.pdf"'},
    )


def _safe_filename(title: str) -> str:
    return "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80] or "document"


@router.post("/ocr")
async def ocr_image(
    file: UploadFile = File(...),
    template_id: str | None = Form(None),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Настоящий OCR (Tesseract) — извлекает сырой текст из фото/скана.
    НЕ понимает структуру документа (это требует AI, см. app/ai/provider.py) —
    честно возвращает только распознанный текст.

    template_id (опционально, п.5 промпта): если передан, дополнительно
    прогоняет распознанный текст через extract_entities() и предлагает
    автозаполнение полей формы (только там, где сущность найдена
    надёжно — деньги/дата/срок/телефон/email), а не просто отдаёт текст
    для ручного переноса.
    """
    data = await file.read()
    try:
        text = extract_text_from_image(data, content_type=file.content_type)
    except OcrError as exc:
        raise api_error(status.HTTP_400_BAD_REQUEST, "OCR_FAILED", str(exc)) from exc

    await add_history_event(user_id, "document_ocr", metadata={"chars_extracted": len(text)})

    suggested_fields: dict[str, str] = {}
    if template_id and text:
        template = await repo.get_template(template_id)
        if template:
            suggested_fields = suggest_field_values(template["fields_schema"], text)

    return {
        "text": text,
        "structural_understanding_available": ai_is_configured(),
        "suggested_fields": suggested_fields,
    }


class RenameRequest(BaseModel):
    title: str


@router.patch("/documents/{document_id}/rename")
async def rename_document(document_id: str, payload: RenameRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    if not payload.title.strip():
        raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_TITLE", "Название не может быть пустым.")
    doc = await repo.rename_document(user_id, document_id, payload.title.strip())
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    return doc


@router.post("/documents/{document_id}/duplicate")
async def duplicate_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    async def _work() -> dict:
        doc = await repo.duplicate_document(user_id, document_id)
        if not doc:
            raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
        await add_history_event(user_id, "document_duplicate", metadata={"document_id": str(doc["id"])})
        return doc

    return await with_idempotency(
        user_id, "duplicate_document", idempotency_key, _work, request_hash=compute_request_hash(document_id)
    )


class ShareRequest(BaseModel):
    expires_in_days: int | None = 7  # по умолчанию неделя, null — бессрочно (осознанный выбор, не публично по умолчанию навсегда)


@router.post("/documents/{document_id}/share")
async def create_share(
    document_id: str,
    payload: ShareRequest,
    user_id: str = Depends(get_current_user_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    async def _work() -> dict:
        share = await repo.create_share_link(user_id, document_id, payload.expires_in_days)
        if not share:
            raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
        await add_history_event(user_id, "document_share_create", metadata={"document_id": document_id})
        return share

    # Идемпотентность (п.7 промпта): двойной клик "Поделиться" с тем же
    # Idempotency-Key не наплодит несколько активных публичных ссылок.
    # request_hash = document_id (из URL) + срок действия — та же защита
    # от переиспользования ключа для другого документа.
    request_hash = compute_request_hash(document_id, payload.expires_in_days)
    return await with_idempotency(user_id, "create_share", idempotency_key, _work, request_hash=request_hash)


@router.get("/documents/{document_id}/shares")
async def get_shares(document_id: str, user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await repo.list_shares(user_id, document_id)


@router.delete("/shares/{share_id}")
async def revoke_share(share_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    revoked = await repo.revoke_share(user_id, share_id)
    if not revoked:
        raise api_error(status.HTTP_404_NOT_FOUND, "SHARE_NOT_FOUND", "Ссылка не найдена или уже отозвана.")
    return {"status": "ok"}


@public_router.get("/{token}")
async def get_shared_document(token: str) -> Response:
    """
    Публичный mobile-first просмотр документа (п.18/49 промпта).
    Раньше отдавал сырой JSON — исправлено: настоящая HTML-страница,
    без авторизации, без React-бандла (лёгкая, п.43), с честными
    состояниями revoked/expired/not_found вместо общего "недоступен".
    """
    try:
        link_status = await repo.get_share_link_status(token)
    except HTTPException:
        # БД временно недоступна — даже в этом случае пользователь не
        # должен увидеть сырой JSON/stack trace (п.18/49 промпта).
        return HTMLResponse(_shared_state_page("Не удалось загрузить документ. Попробуйте открыть ссылку позже."), status_code=503)

    if link_status == "expired":
        return HTMLResponse(_shared_state_page("Срок действия ссылки истёк."), status_code=410)
    if link_status == "revoked":
        return HTMLResponse(_shared_state_page("Ссылка была отозвана владельцем."), status_code=410)
    if link_status == "not_found":
        return HTMLResponse(_shared_state_page("Документ недоступен."), status_code=404)

    try:
        doc = await repo.get_document_by_share_token(token)
    except HTTPException:
        return HTMLResponse(_shared_state_page("Не удалось загрузить документ. Попробуйте открыть ссылку позже."), status_code=503)

    if not doc:
        # Гонка между проверкой статуса и получением документа (например,
        # ссылку отозвали между двумя запросами) — тот же честный экран.
        return HTMLResponse(_shared_state_page("Документ недоступен."), status_code=404)

    return HTMLResponse(_shared_document_page(doc, token))


@public_router.get("/{token}/download/{fmt}")
async def download_shared_document(token: str, fmt: str) -> Response:
    if fmt not in ("docx", "pdf"):
        return HTMLResponse(_shared_state_page("Неподдерживаемый формат."), status_code=400)

    try:
        doc = await repo.get_document_by_share_token(token)
    except HTTPException:
        return HTMLResponse(_shared_state_page("Не удалось загрузить документ. Попробуйте открыть ссылку позже."), status_code=503)

    if not doc:
        return HTMLResponse(_shared_state_page("Документ недоступен."), status_code=404)

    if fmt == "docx":
        data = render_docx(doc["title"], doc["content_blocks"])
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        data = render_pdf(doc["title"], doc["content_blocks"])
        media_type = "application/pdf"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{_safe_filename(doc["title"])}.{fmt}"'},
    )


def _shared_state_page(message: str) -> str:
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>AI Docs</title>
<style>{_SHARED_CSS}</style></head>
<body><div class="wrap"><div class="card state-card">
<p class="brand">AI Docs</p>
<p class="state-message">{message}</p>
</div></div></body></html>"""


def _shared_document_page(doc: dict, token: str) -> str:
    date_str = doc["created_at"].strftime("%d.%m.%Y") if hasattr(doc["created_at"], "strftime") else str(doc["created_at"])[:10]
    blocks_html = ""
    for block in doc.get("content_blocks") or []:
        block_type = block.get("type")
        text = _html_escape(block.get("text", ""))
        if block_type == "spacer":
            blocks_html += '<div class="spacer"></div>'
        elif block_type == "heading_center":
            blocks_html += f'<p class="h-center">{text}</p>'
        elif block_type == "heading":
            blocks_html += f'<p class="h">{text}</p>'
        elif block_type == "paragraph_right":
            blocks_html += f'<p class="p-right">{text}</p>'
        elif block_type == "signature_line":
            blocks_html += f'<p class="signature">{text} &nbsp;&nbsp; _______________</p>'
        else:
            blocks_html += f'<p class="p">{text}</p>'

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{_html_escape(doc["title"])} — AI Docs</title>
<style>{_SHARED_CSS}</style></head>
<body><div class="wrap">
<p class="brand">AI Docs</p>
<div class="card doc-card">
  <h1 class="doc-title">{_html_escape(doc["title"])}</h1>
  <p class="doc-date">{date_str}</p>
  <div class="divider"></div>
  <div class="doc-body">{blocks_html}</div>
</div>
<div class="actions">
  <a class="btn" href="/api/v1/aidocs/shared/{token}/download/pdf">Скачать PDF</a>
  <a class="btn btn-outline" href="/api/v1/aidocs/shared/{token}/download/docx">Скачать DOCX</a>
</div>
</div></body></html>"""


def _html_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_SHARED_CSS = """
:root{color-scheme:dark;}
*{box-sizing:border-box;}
body{margin:0;background:#0B0B10;color:#F5F5F7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased;}
.wrap{max-width:480px;margin:0 auto;padding:24px 16px 40px;min-height:100vh;}
.brand{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6C63FF;text-align:center;margin:0 0 18px;}
.card{background:#131319;border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:20px;}
.state-card{margin-top:20vh;text-align:center;padding:32px 20px;}
.state-message{font-size:15px;color:rgba(245,245,247,.75);margin:8px 0 0;}
.doc-title{font-size:19px;font-weight:700;margin:0;text-align:center;}
.doc-date{font-size:12px;color:rgba(245,245,247,.5);text-align:center;margin:4px 0 0;}
.divider{height:1px;background:rgba(255,255,255,.08);margin:16px 0;}
.doc-body{background:#fff;color:#161616;border-radius:14px;padding:20px;font-family:Georgia,serif;}
.doc-body .p{font-size:13px;line-height:1.6;text-align:justify;margin:6px 0;}
.doc-body .p-right{font-size:12.5px;text-align:right;margin:4px 0;}
.doc-body .h{font-weight:700;font-size:13.5px;margin:14px 0 4px;}
.doc-body .h-center{font-weight:700;font-size:14.5px;text-align:center;margin:6px 0;}
.doc-body .signature{font-size:12.5px;margin-top:16px;}
.doc-body .spacer{height:12px;}
.actions{display:flex;gap:8px;margin-top:16px;}
.btn{flex:1;text-align:center;padding:13px;border-radius:14px;background:#6C63FF;color:#fff;text-decoration:none;font-weight:700;font-size:13.5px;}
.btn-outline{background:#131319;border:1px solid rgba(255,255,255,.14);color:#F5F5F7;}
"""


@router.post("/documents/import")
async def import_document(
    file: UploadFile = File(...),
    title: str | None = None,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Создаёт документ из загруженного DOCX/PDF. ЧЕСТНО: только реальное
    извлечение текста (python-docx/pypdf) — без AI-понимания структуры,
    без AI-улучшений (см. app/ai/provider.py, недоступно без ключа).
    """
    data = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".docx"):
            paragraphs = extract_text_from_docx_file(data)
        elif filename.endswith(".pdf"):
            paragraphs = extract_text_from_pdf_file(data)
        else:
            raise api_error(
                status.HTTP_400_BAD_REQUEST, "UNSUPPORTED_FORMAT", "Поддерживаются только файлы .docx и .pdf."
            )
    except ImportError_ as exc:
        raise api_error(status.HTTP_400_BAD_REQUEST, "IMPORT_FAILED", str(exc)) from exc

    content_blocks = [{"type": "paragraph", "text": p} for p in paragraphs]
    doc_title = (title or file.filename or "Импортированный документ").strip()

    doc = await repo.create_document(user_id, None, doc_title, "universal", {}, content_blocks)
    await add_history_event(
        user_id, "document_import", metadata={"document_id": str(doc["id"]), "source_filename": file.filename}
    )
    return doc


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    document_id: str | None = None  # чтобы редактировать конкретный открытый документ через чат (п.1 промпта)


@router.post("/chat")
async def chat(payload: ChatRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Document Intelligence Engine — rule-based (regex/scoring), БЕЗ
    внешнего AI API (см. app/document_intelligence/). Живой диалог,
    но интеллект — сопоставление с образцом, не понимание языка.

    Чтение+обработка+запись состояния диалога выполняются атомарно
    (SELECT ... FOR UPDATE в одной транзакции, conv_repo.
    with_locked_conversation) — защита от гонки при двойном/почти
    одновременном сообщении (п.34 промпта: идемпотентность операций
    создания документа не должна держаться только на disabled-кнопке
    фронтенда).

    document_id (опционально): фронтенд передаёт id открытого документа,
    когда чат вызывается из его превью — это включает EDIT_DOCUMENT/
    CHANGE_FIELD (п.1 промпта: редактирование существующего документа
    через чат). Значение сохраняется в диалоге и переживает последующие
    сообщения без document_id (coalesce на уровне conv_repo).
    """
    templates = await repo.list_templates_full()
    templates_by_key = {t["template_key"]: t for t in templates}
    templates_by_id = {str(t["id"]): t for t in templates}

    reply_holder: dict = {}
    created_document_holder: dict = {}
    edited_document_holder: dict = {}

    async def mutate(conv_row: dict):
        target_document_id = payload.document_id or (
            str(conv_row["document_id"]) if conv_row.get("document_id") else None
        )
        target_document: dict | None = None
        if target_document_id:
            target_document = await repo.get_document(user_id, target_document_id)
            if not target_document:
                # чужой/удалённый документ — не поднимаем ошибку всего чата,
                # просто честно теряем контекст редактирования, agent сам
                # ответит "не удалось найти документ" при попытке его править
                target_document_id = None

        agent = DocumentAgent(
            lambda key: templates_by_key.get(key),
            None,
            get_document_by_id=(lambda doc_id, _doc=target_document: _doc if _doc and str(_doc["id"]) == str(doc_id) else None),
            get_template_by_id=lambda template_id: templates_by_id.get(str(template_id)),
        )

        state = ConversationState(
            status=conv_row["status"],
            intent=conv_row["intent"],
            template_key=conv_row["template_key"],
            field_values=dict(conv_row["field_values"] or {}),
            awaiting_field=conv_row["awaiting_field"],
            document_id=target_document_id,
        )

        reply = agent.handle_message(state, payload.message)
        reply_holder["reply"] = reply
        reply_holder["state_status"] = state.status

        messages = list(conv_row["messages"] or [])
        messages.append({"role": "user", "text": payload.message, "created_at": conv_repo.now_iso()})
        messages.append({"role": "agent", "text": reply.message, "created_at": conv_repo.now_iso()})

        created_document = None
        if reply.ready_to_create and state.status == "done" and state.template_key:
            template = templates_by_key.get(state.template_key)
            if template:
                content_blocks = fill_template(template["body_template"], state.field_values)
                created_document = await repo.create_document(
                    user_id, template["id"], template["name"], template["category"], state.field_values, content_blocks
                )
                await add_history_event(
                    user_id, "document_create_via_chat",
                    metadata={"document_id": str(created_document["id"]), "template_key": state.template_key},
                )
                created_document_holder["doc"] = created_document

        if reply.document_edit:
            updated_document = await repo.apply_edit(
                user_id, reply.document_edit.document_id, reply.document_edit.content_blocks, reply.document_edit.note
            )
            if updated_document:
                await add_history_event(
                    user_id,
                    "document_edit_via_chat",
                    metadata={"document_id": reply.document_edit.document_id, "note": reply.document_edit.note},
                )
                edited_document_holder["doc"] = updated_document

        new_values = {
            "status": state.status,
            "intent": state.intent,
            "template_key": state.template_key,
            "field_values": state.field_values,
            "awaiting_field": state.awaiting_field,
            "messages": messages,
            "document_id": str(created_document["id"]) if created_document else target_document_id,
        }
        return new_values, None

    updated_conv, _ = await conv_repo.with_locked_conversation(user_id, payload.conversation_id, mutate)
    if updated_conv is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "CONVERSATION_NOT_FOUND", "Диалог не найден.")

    reply = reply_holder["reply"]
    created_document = created_document_holder.get("doc")
    edited_document = edited_document_holder.get("doc")

    return {
        "conversation_id": str(updated_conv["id"]),
        "reply": reply.message,
        "status": reply_holder["state_status"],
        "quick_actions": reply.quick_actions,
        "ready_to_create": reply.ready_to_create,
        "document": created_document,
        "edited_document": edited_document,
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    conv = await conv_repo.get_conversation(user_id, conversation_id)
    if not conv:
        raise api_error(status.HTTP_404_NOT_FOUND, "CONVERSATION_NOT_FOUND", "Диалог не найден.")
    return conv


@router.get("/conversations/active/current")
async def get_active_conversation(user_id: str = Depends(get_current_user_id)) -> dict:
    """Для восстановления состояния после закрытия Mini App (п.25/26 промпта — autosave/conversation state)."""
    return await conv_repo.get_or_create_active_conversation(user_id)


@router.post("/documents/{document_id}/analyze")
async def analyze_document_route(document_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    """Document Quality Check — rule-based (п.21-22 промпта), не юридический AI-анализ."""
    doc = await repo.get_document(user_id, document_id)
    if not doc:
        raise api_error(status.HTTP_404_NOT_FOUND, "DOCUMENT_NOT_FOUND", "Документ не найден.")
    report = analyze_document(doc["content_blocks"])
    await add_history_event(user_id, "document_analyze", metadata={"document_id": document_id, "status": report.status})
    return {
        "status": report.status,
        "disclaimer": report.disclaimer,
        "issues": [
            {"severity": i.severity, "category": i.category, "message": i.message, "suggestion": i.suggestion}
            for i in report.issues
        ],
    }
