import pytest

from app.document_engine.docx_renderer import render_docx
from app.document_engine.pdf_renderer import render_pdf
from app.document_engine.import_reader import (
    ImportError_,
    extract_text_from_docx_file,
    extract_text_from_pdf_file,
)

BLOCKS = [
    {"type": "paragraph", "text": "Первый абзац документа."},
    {"type": "paragraph", "text": "Второй абзац с деталями и цифрами 12345."},
]


def test_extract_text_from_docx_returns_real_paragraphs():
    data = render_docx("Импортированный документ", BLOCKS)
    paragraphs = extract_text_from_docx_file(data)
    assert "Первый абзац документа." in paragraphs
    assert "Второй абзац с деталями и цифрами 12345." in paragraphs
    assert "Импортированный документ" in paragraphs  # заголовок тоже параграф


def test_extract_text_from_pdf_returns_real_paragraphs():
    data = render_pdf("Импортированный документ", BLOCKS)
    paragraphs = extract_text_from_pdf_file(data)
    joined = " ".join(paragraphs)
    assert "Первый абзац документа." in joined
    assert "12345" in joined


def test_extract_text_from_docx_rejects_garbage():
    with pytest.raises(ImportError_):
        extract_text_from_docx_file(b"this is definitely not a docx file")


def test_extract_text_from_pdf_rejects_garbage():
    with pytest.raises(ImportError_):
        extract_text_from_pdf_file(b"this is definitely not a pdf file")


def test_extract_text_from_docx_rejects_oversized():
    huge = b"\x00" * (16 * 1024 * 1024)
    with pytest.raises(ImportError_):
        extract_text_from_docx_file(huge)


def test_extract_text_from_pdf_rejects_encrypted():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    import io

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 700, "secret")
    c.save()
    plain_pdf = buf.getvalue()

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(plain_pdf))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("password123")
    encrypted_buf = io.BytesIO()
    writer.write(encrypted_buf)

    with pytest.raises(ImportError_):
        extract_text_from_pdf_file(encrypted_buf.getvalue())
