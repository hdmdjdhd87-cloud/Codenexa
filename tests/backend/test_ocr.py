import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.document_engine.ocr import OcrError, extract_text_from_image

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _render_text_image(text: str) -> bytes:
    img = Image.new("RGB", (700, 120), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 28)
    draw.text((15, 40), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extract_text_from_image_cyrillic():
    image_bytes = _render_text_image("Съезд состоится завтра")
    text = extract_text_from_image(image_bytes, content_type="image/png")
    assert "Съезд" in text or "състоится" in text.lower() or "завтра" in text.lower()
    assert len(text) > 3


def test_extract_text_rejects_non_image_bytes():
    with pytest.raises(OcrError):
        extract_text_from_image(b"this is not an image at all", content_type="image/png")


def test_extract_text_rejects_oversized_file():
    huge = b"\x00" * (11 * 1024 * 1024)
    with pytest.raises(OcrError):
        extract_text_from_image(huge, content_type="image/png")


def test_extract_text_rejects_disallowed_content_type():
    image_bytes = _render_text_image("test")
    with pytest.raises(OcrError):
        extract_text_from_image(image_bytes, content_type="application/pdf")


def test_extract_text_accepts_none_content_type():
    # content_type может отсутствовать (не все клиенты его присылают) — не должно падать из-за этого
    image_bytes = _render_text_image("ok")
    text = extract_text_from_image(image_bytes, content_type=None)
    assert isinstance(text, str)
