from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.auth.middleware import get_current_user_id
from app.repositories import aidocs_repository as repo
from app.repositories.history_repository import add_history_event
from app.document_engine.template_fill import fill_template, validate_required_fields
from app.document_engine.docx_renderer import render_docx
from app.document_engine.pdf_renderer import render_pdf
from app.document_engine.qa import DocumentQAError, check_docx, check_pdf
from app.ai.provider import ai_is_configured
from app.utils.errors import api_error
from fastapi import status

router = APIRouter(prefix="/api/v1/aidocs", tags=["aidocs"])


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
async def create_document(payload: CreateDocumentRequest, user_id: str = Depends(get_current_user_id)) -> dict:
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

    content_blocks = fill_template(template["body_template"], payload.field_values)
    doc = await repo.create_document(
        user_id, template["id"], payload.title, template["category"], payload.field_values, content_blocks
    )
    await add_history_event(user_id, "document_create", metadata={"document_id": str(doc["id"]), "title": doc["title"]})
    return doc


@router.get("/documents")
async def get_documents(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await repo.list_documents(user_id)


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
