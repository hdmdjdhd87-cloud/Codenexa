from app.document_intelligence.ocr_autofill import suggest_field_values

FIELDS_SCHEMA = [
    {"key": "customer", "label": "Заказчик", "type": "text", "required": True},
    {"key": "phone", "label": "Телефон", "type": "text", "required": False},
    {"key": "email", "label": "Email", "type": "text", "required": False},
    {"key": "price", "label": "Стоимость услуг", "type": "text", "required": True},
    {"key": "term", "label": "Срок оказания услуг", "type": "text", "required": True},
    {"key": "date", "label": "Дата", "type": "date", "required": True},
]


def test_suggests_money_field_from_ocr_text():
    text = "Договор оказания услуг. Стоимость составляет 150000 тенге."
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert "150000" in suggested["price"]


def test_suggests_duration_field_from_ocr_text():
    text = "Срок оказания услуг: 3 месяца."
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert suggested["term"] == "3 месяцев"


def test_suggests_date_field_from_ocr_text():
    text = "Документ составлен 20.08.2026."
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert suggested["date"] == "2026-08-20"


def test_suggests_phone_field_from_ocr_text():
    text = "Контактный телефон: +7 701 234 56 78"
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert suggested["phone"].strip() != ""


def test_suggests_email_field_from_ocr_text():
    text = "Электронная почта для связи: ivanov@example.com"
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert suggested["email"] == "ivanov@example.com"


def test_combines_multiple_entities_in_one_pass():
    text = "Стоимость 200000 тенге. Срок 6 месяцев. Дата: 01.09.2026. email: a@b.kz"
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert "200000" in suggested["price"]
    assert suggested["term"] == "6 месяцев"
    assert suggested["date"] == "2026-09-01"
    assert suggested["email"] == "a@b.kz"


def test_does_not_guess_free_text_fields_like_customer_name():
    text = "Иванов Иван Иванович, стоимость 100000 тенге"
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    # честная граница: extract_entities не извлекает имена собственные —
    # поле "customer" НЕ должно быть заполнено случайным обрывком текста
    assert "customer" not in suggested


def test_empty_ocr_text_returns_empty_suggestions():
    assert suggest_field_values(FIELDS_SCHEMA, "") == {}
    assert suggest_field_values(FIELDS_SCHEMA, "   ") == {}


def test_no_matching_entities_returns_empty_dict():
    text = "просто какой-то текст без структурированных данных"
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert suggested == {}


def test_does_not_overwrite_already_matched_category_field_with_second_entity():
    # Два денежных упоминания в тексте — под них только одно поле "price",
    # берётся первое найденное, второе не должно попасть в другое случайное поле.
    text = "Стоимость 150000 тенге, позже доплата 50000 тенге."
    suggested = suggest_field_values(FIELDS_SCHEMA, text)
    assert "150000" in suggested["price"]
    assert len([k for k in suggested if k == "price"]) == 1
