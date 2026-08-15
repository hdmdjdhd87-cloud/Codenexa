from app.document_engine.template_fill import fill_template, validate_required_fields
from app.document_engine.docx_renderer import render_docx
from app.document_engine.pdf_renderer import render_pdf
from app.document_engine.qa import DocumentQAError, check_docx, check_pdf

BODY_TEMPLATE = [
    {"type": "heading_center", "text": "ЗАЯВЛЕНИЕ"},
    {"type": "paragraph", "text": "Я, {{name}}, прошу {{request}}."},
    {"type": "paragraph", "text": "Основание: {{reason}}"},
    {"type": "spacer"},
    {"type": "signature_line", "text": "{{name}}"},
]


def test_fill_template_substitutes_placeholders():
    values = {"name": "Иванов Иван", "request": "предоставить справку", "reason": "для банка"}
    blocks = fill_template(BODY_TEMPLATE, values)
    joined = " ".join(b["text"] for b in blocks if b["text"])
    assert "Иванов Иван" in joined
    assert "предоставить справку" in joined
    assert "{{" not in joined  # ни один плейсхолдер не остался незаполненным


def test_fill_template_drops_empty_optional_lines():
    values = {"name": "Иванов Иван", "request": "справку", "reason": ""}
    blocks = fill_template(BODY_TEMPLATE, values)
    # "Основание: " без содержания не должно попасть в итоговые блоки
    assert not any(b["text"].strip() == "Основание:" for b in blocks)


def test_validate_required_fields_reports_missing():
    schema = [
        {"key": "name", "label": "ФИО", "required": True},
        {"key": "comment", "label": "Комментарий", "required": False},
    ]
    missing = validate_required_fields(schema, {"name": "", "comment": "x"})
    assert missing == ["ФИО"]


def test_validate_required_fields_all_filled():
    schema = [{"key": "name", "label": "ФИО", "required": True}]
    assert validate_required_fields(schema, {"name": "Иванов"}) == []


def test_render_docx_produces_valid_file():
    blocks = fill_template(BODY_TEMPLATE, {"name": "Петров П.П.", "request": "отпуск", "reason": "заявление"})
    data = render_docx("Заявление", blocks)
    assert len(data) > 1000
    result = check_docx(data)
    assert result["opens"] is True
    assert result["has_text"] is True


def test_render_pdf_produces_valid_file_with_cyrillic():
    blocks = fill_template(BODY_TEMPLATE, {"name": "Сидорова А.А.", "request": "справку", "reason": "по месту работы"})
    data = render_pdf("Заявление", blocks)
    assert len(data) > 500
    result = check_pdf(data)
    assert result["opens"] is True
    assert result["has_text"] is True
    assert result["empty_pages"] == 0


def test_render_pdf_cyrillic_extractable_correctly():
    blocks = [{"type": "paragraph", "text": "Кириллица должна извлекаться корректно"}]
    data = render_pdf("Тест", blocks)
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(data))
    text = reader.pages[0].extract_text()
    assert "Кириллица" in text
    assert "должна извлекаться корректно" in text


def test_qa_rejects_empty_pdf_gracefully():
    # Пустой content_blocks -> только заголовок, но не должно падать с исключением наружу
    data = render_pdf("Пустой документ", [])
    result = check_pdf(data)
    assert result["opens"] is True
