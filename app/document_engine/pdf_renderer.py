"""
Генерация настоящего PDF из content_blocks.

Требование спецификации (п.16): корректная кириллица, без обрезанного
текста, без пустых страниц, с переносами. reportlab по умолчанию не
умеет кириллицу (Helvetica — latin-1) — регистрируем DejaVuSans
(TrueType, полный юникод), который реально есть в системе.
"""
from __future__ import annotations

import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_NAME = "CodeNexaBody"
_font_registered = False


def _ensure_font_registered() -> str:
    global _font_registered
    if _font_registered:
        return FONT_NAME
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            _font_registered = True
            return FONT_NAME
    # Честный fallback: если шрифта нет в окружении (например, другой
    # деплой), используем встроенный Helvetica — кириллица тогда не
    # отобразится корректно. Это должно быть заметно на этапе QA, а не
    # тихо проглочено.
    return "Helvetica"


def render_pdf(title: str, content_blocks: list[dict]) -> bytes:
    font = _ensure_font_registered()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    title_style = ParagraphStyle("Title", fontName=font, fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=16)
    heading_style = ParagraphStyle("Heading", fontName=font, fontSize=13, leading=17, spaceBefore=10, spaceAfter=6)
    heading_center_style = ParagraphStyle("HeadingCenter", parent=heading_style, alignment=TA_CENTER)
    body_style = ParagraphStyle("Body", fontName=font, fontSize=11, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=8)
    right_style = ParagraphStyle("Right", parent=body_style, alignment=TA_RIGHT)
    signature_style = ParagraphStyle("Signature", fontName=font, fontSize=11, leading=15.5, spaceBefore=18)

    story = [Paragraph(_escape(title), title_style)]

    for block in content_blocks:
        block_type = block.get("type")
        text = _escape(block.get("text", ""))

        if block_type == "spacer":
            story.append(Spacer(1, 10))
        elif block_type == "heading":
            story.append(Paragraph(text, heading_style))
        elif block_type == "heading_center":
            story.append(Paragraph(text, heading_center_style))
        elif block_type == "paragraph_right":
            story.append(Paragraph(text, right_style))
        elif block_type == "signature_line":
            story.append(Paragraph(f"{text}&nbsp;&nbsp;&nbsp;_______________ /_______________/", signature_style))
        else:
            story.append(Paragraph(text, body_style))

    doc.build(story)
    return buf.getvalue()


def _escape(text: str) -> str:
    # reportlab Paragraph использует mini-XML разметку — экранируем
    # пользовательский текст, чтобы случайные <, >, & не ломали рендер.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
