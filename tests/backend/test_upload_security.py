"""
Тесты защиты от zip-bomb (DOCX) и избыточного числа страниц (PDF) —
P0-05 из аудита 22.08.2026: "DOCX: zip bomb detection, extracted-size
limit" + "PDF: page count... limits".
"""
import io
import zipfile

import pytest
from pypdf import PdfWriter

from app.document_engine.import_reader import (
    ImportError_,
    MAX_PDF_PAGES,
    extract_text_from_docx_file,
    extract_text_from_pdf_file,
    _check_docx_zip_safety,
)
from app.document_engine.docx_renderer import render_docx


def _build_zip(entries: list[tuple[str, bytes]], compress: bool = True) -> bytes:
    buf = io.BytesIO()
    method = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(buf, "w", method) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return buf.getvalue()


def test_legitimate_docx_passes_zip_safety_check():
    data = render_docx("Обычный документ", [{"type": "paragraph", "text": "Текст"}])
    _check_docx_zip_safety(data)  # не должно бросить исключение


def test_zip_bomb_high_compression_ratio_rejected():
    # 5 МБ хорошо сжимаемых (повторяющихся) данных в один ZIP-entry —
    # реалистичный, компактный zip-bomb паттерн: файл на диске маленький
    # (несколько КБ после сжатия), а распакованный объём в сотни раз больше.
    huge_compressible = b"A" * (5 * 1024 * 1024)
    data = _build_zip([("word/document.xml", huge_compressible)], compress=True)
    with pytest.raises(ImportError_, match="аномальное сжатие|распакованного размера"):
        _check_docx_zip_safety(data)


def test_extract_text_from_docx_rejects_zip_bomb_before_parsing():
    huge_compressible = b"B" * (5 * 1024 * 1024)
    data = _build_zip([("word/document.xml", huge_compressible)], compress=True)
    with pytest.raises(ImportError_):
        extract_text_from_docx_file(data)


def test_too_many_zip_entries_rejected():
    entries = [(f"file_{i}.xml", b"x") for i in range(2500)]
    data = _build_zip(entries, compress=False)
    with pytest.raises(ImportError_, match="вложений"):
        _check_docx_zip_safety(data)


def test_normal_number_of_entries_and_reasonable_size_passes():
    # Похоже на реальный DOCX по структуре (несколько XML-частей
    # разумного размера, без сжатия — не должно триггерить ratio-check
    # для маленьких файлов, где compress_size≈file_size).
    entries = [(f"part_{i}.xml", b"<xml>some content here</xml>" * 10) for i in range(20)]
    data = _build_zip(entries, compress=False)
    _check_docx_zip_safety(data)  # не должно бросить исключение


def test_not_a_zip_file_rejected_with_clear_error():
    with pytest.raises(ImportError_, match="ZIP-архив"):
        _check_docx_zip_safety(b"this is definitely not a zip file at all")


def test_pdf_within_page_limit_accepted():
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    # Пустые страницы без текста -> extract_text_from_pdf_file упадёт с
    # "не удалось извлечь текст", а не с лимитом страниц — проверяем это
    # отдельно, здесь важно, что MAX_PDF_PAGES НЕ триггерится раньше времени.
    with pytest.raises(ImportError_, match="не удалось извлечь текст|скан"):
        extract_text_from_pdf_file(buf.getvalue())


def test_pdf_exceeding_page_limit_rejected():
    writer = PdfWriter()
    for _ in range(MAX_PDF_PAGES + 1):
        writer.add_blank_page(width=50, height=50)
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ImportError_, match="страниц"):
        extract_text_from_pdf_file(buf.getvalue())


def test_pillow_decompression_bomb_protection_not_disabled():
    # P0-05 из аудита: Pillow защищает от decompression bomb ПО
    # УМОЛЧАНИЮ через Image.MAX_IMAGE_PIXELS — частая случайная
    # "починка" предупреждения (`Image.MAX_IMAGE_PIXELS = None`)
    # полностью отключает эту защиту. Regression-тест, а не
    # функциональность, которую мы сами добавили.
    from PIL import Image

    assert Image.MAX_IMAGE_PIXELS is not None
    assert Image.MAX_IMAGE_PIXELS > 0
