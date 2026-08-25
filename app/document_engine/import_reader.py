"""
Импорт существующего DOCX/PDF (п.9 промпта — "работа с существующим
документом"). Реализована только честная часть: настоящее извлечение
текста через python-docx/pypdf. AI-часть (понять структуру, сохранить
смысл, предложить улучшения) архитектурно относится к
app/ai/provider.py и без ключа LLM недоступна — см. AIUnavailableError.
"""
from __future__ import annotations

import io
import zipfile

from docx import Document as DocxDocument
from pypdf import PdfReader

MAX_IMPORT_BYTES = 15 * 1024 * 1024  # 15 MB

# P0-05 из аудита 22.08.2026 ("Upload security"): "DOCX: zip bomb
# detection, extracted-size limit, relationship/resource checks" +
# "PDF: page count, object count... limits". DOCX — это ZIP-архив;
# python-docx распаковывает содержимое без каких-либо проверок размера —
# компактный (несколько КБ) вредоносный архив может распаковаться в
# гигабайты и исчерпать память процесса. Проверяем метаданные ZIP
# (file_size/compress_size из центральной директории) БЕЗ реальной
# распаковки — это дёшево и не требует читать сжатые данные вообще.
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB — щедрый запас
# для легитимного DOCX с embedded-изображениями, но далеко от "бомбы"
MAX_DOCX_ZIP_ENTRIES = 2000  # легитимный DOCX обычно имеет ~15-30 записей
MAX_DOCX_COMPRESSION_RATIO = 100  # общепринятый эвристический порог для zip-bomb detection

MAX_PDF_PAGES = 500  # щедро для любого реального делового/юридического документа


class ImportError_(Exception):
    pass


def _check_docx_zip_safety(data: bytes) -> None:
    """
    Инспектирует ZIP-метаданные DOCX-файла ДО того, как python-docx
    начнёт его распаковывать. Три независимых проверки — компактный
    zip-bomb обычно эксплуатирует ОДНУ из них, но легитимный документ
    не должен упираться ни в одну при разумных лимитах выше.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_DOCX_ZIP_ENTRIES:
                raise ImportError_("Файл повреждён или имеет подозрительную структуру (слишком много вложений).")

            total_uncompressed = 0
            for info in infos:
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                    raise ImportError_("Файл повреждён или имеет подозрительную структуру (превышен лимит распакованного размера).")
                # compress_size == 0 для директорий/пустых записей — не делим на ноль
                if info.compress_size > 0 and info.file_size / info.compress_size > MAX_DOCX_COMPRESSION_RATIO:
                    raise ImportError_("Файл повреждён или имеет подозрительную структуру (аномальное сжатие).")
    except zipfile.BadZipFile as exc:
        raise ImportError_("Не удалось открыть DOCX-файл: повреждённый или не ZIP-архив.") from exc


def extract_text_from_docx_file(data: bytes) -> list[str]:
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportError_("Файл слишком большой (максимум 15 МБ).")

    _check_docx_zip_safety(data)

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

    # len(reader.pages) читает только метаданные структуры страниц
    # (page tree), не рендерит и не извлекает текст — дёшево проверить
    # ДО тяжёлого извлечения текста ниже (P0-05: "PDF: page count...
    # limits").
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ImportError_(f"В PDF слишком много страниц (максимум {MAX_PDF_PAGES}).")

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
