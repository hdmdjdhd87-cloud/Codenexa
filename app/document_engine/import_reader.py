"""
Импорт существующего DOCX/PDF (п.9 промпта — "работа с существующим
документом"). Реализована только честная часть: настоящее извлечение
текста через python-docx/pypdf. AI-часть (понять структуру, сохранить
смысл, предложить улучшения) архитектурно относится к
app/ai/provider.py и без ключа LLM недоступна — см. AIUnavailableError.
"""
from __future__ import annotations

import io

from docx import Document as DocxDocument
from pypdf import PdfReader

MAX_IMPORT_BYTES = 15 * 1024 * 1024  # 15 MB


class ImportError_(Exception):
    pass


def extract_text_from_docx_file(data: bytes) -> list[str]:
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportError_("Файл слишком большой (максимум 15 МБ).")
    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ImportError_(f"Не удалось открыть DOCX-файл: {exc}") from exc

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise ImportError_("В документе не найден текст.")
    return paragraphs


def extract_text_from_pdf_file(data: bytes) -> list[str]:
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportError_("Файл слишком большой (максимум 15 МБ).")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ImportError_(f"Не удалось открыть PDF-файл: {exc}") from exc

    if reader.is_encrypted:
        raise ImportError_("PDF защищён паролем — сначала снимите защиту.")

    paragraphs: list[str] = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            # extract_text() отдаёт страницу одним блоком — делим по
            # переносам строк, чтобы получить что-то похожее на абзацы.
            paragraphs.extend([line.strip() for line in text.split("\n") if line.strip()])

    if not paragraphs:
        raise ImportError_("Не удалось извлечь текст из PDF (возможно, это скан без текстового слоя — используйте загрузку фото для OCR).")
    return paragraphs
