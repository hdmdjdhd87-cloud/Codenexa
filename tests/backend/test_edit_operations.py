from app.document_intelligence.edit_operations import (
    parse_edit_command,
    apply_replace_text,
    apply_add_section,
    apply_remove_section,
    parse_change_field_command,
    find_target_field,
)


def _p(text: str, block_type: str = "paragraph") -> dict:
    return {"type": block_type, "text": text}


TEMPLATE_SCHEMA = [
    {"key": "customer", "label": "Заказчик", "type": "text", "required": True},
    {"key": "price", "label": "Стоимость услуг", "type": "text", "required": True},
    {"key": "term", "label": "Срок оказания услуг", "type": "text", "required": True},
    {"key": "date", "label": "Дата", "type": "date", "required": True},
]


# ---------- parse_edit_command ----------

def test_parse_replace_command():
    parsed = parse_edit_command("замени 150000 тенге на 200000 тенге")
    assert parsed.op == "replace_text"
    assert parsed.old_text == "150000 тенге"
    assert parsed.new_text == "200000 тенге"


def test_parse_add_section_command_with_colon():
    parsed = parse_edit_command("добавь пункт: Гарантия 12 месяцев")
    assert parsed.op == "add_section"
    assert parsed.new_text == "Гарантия 12 месяцев"


def test_parse_add_section_command_with_space_only():
    parsed = parse_edit_command("добавь раздел Условия оплаты")
    assert parsed.op == "add_section"
    assert parsed.new_text == "Условия оплаты"


def test_parse_remove_section_command():
    parsed = parse_edit_command("удали пункт: Гарантия 12 месяцев")
    assert parsed.op == "remove_section"
    assert parsed.old_text == "Гарантия 12 месяцев"


def test_parse_remove_section_command_ubери_synonym():
    parsed = parse_edit_command("убери абзац: старое условие")
    assert parsed.op == "remove_section"
    assert parsed.old_text == "старое условие"


def test_parse_unrecognized_command():
    parsed = parse_edit_command("отредактируй как считаешь нужным")
    assert parsed.op == "unrecognized"


# ---------- apply_replace_text ----------

def test_apply_replace_text_finds_and_replaces():
    blocks = [_p("Стоимость услуг составляет 150000 тенге.")]
    new_blocks, replaced = apply_replace_text(blocks, "150000 тенге", "200000 тенге")
    assert replaced == 1
    assert new_blocks[0]["text"] == "Стоимость услуг составляет 200000 тенге."


def test_apply_replace_text_is_case_insensitive():
    blocks = [_p("ЗАКАЗЧИК: Иванов")]
    new_blocks, replaced = apply_replace_text(blocks, "заказчик", "Заказчик")
    assert replaced == 1
    assert "Заказчик" in new_blocks[0]["text"]


def test_apply_replace_text_not_found_returns_zero():
    blocks = [_p("Стоимость услуг составляет 150000 тенге.")]
    new_blocks, replaced = apply_replace_text(blocks, "999999", "111111")
    assert replaced == 0
    assert new_blocks[0]["text"] == blocks[0]["text"]  # документ не тронут


def test_apply_replace_text_across_multiple_blocks():
    blocks = [_p("Иванов подписал документ."), _p("Иванов согласен с условиями.")]
    new_blocks, replaced = apply_replace_text(blocks, "Иванов", "Петров")
    assert replaced == 2
    assert new_blocks[0]["text"] == "Петров подписал документ."
    assert new_blocks[1]["text"] == "Петров согласен с условиями."


def test_apply_replace_text_preserves_block_type():
    blocks = [_p("РАСПИСКА", "heading_center")]
    new_blocks, replaced = apply_replace_text(blocks, "РАСПИСКА", "СПРАВКА")
    assert replaced == 1
    assert new_blocks[0]["type"] == "heading_center"


def test_apply_replace_text_does_not_mutate_input():
    blocks = [_p("Оригинал")]
    apply_replace_text(blocks, "Оригинал", "Изменено")
    assert blocks[0]["text"] == "Оригинал"


# ---------- apply_add_section ----------

def test_apply_add_section_appends_block():
    blocks = [_p("Первый пункт")]
    new_blocks = apply_add_section(blocks, "Второй пункт")
    assert len(new_blocks) == 2
    assert new_blocks[-1] == {"type": "paragraph", "text": "Второй пункт"}
    assert blocks == [_p("Первый пункт")]  # не мутирует исходный список


def test_apply_add_section_custom_block_type():
    blocks = []
    new_blocks = apply_add_section(blocks, "Дополнение", block_type="signature_line")
    assert new_blocks[-1]["type"] == "signature_line"


# ---------- apply_remove_section ----------

def test_apply_remove_section_removes_matching_block():
    blocks = [_p("Первый пункт"), _p("Гарантия 12 месяцев"), _p("Третий пункт")]
    new_blocks, removed = apply_remove_section(blocks, "Гарантия")
    assert removed == 1
    assert len(new_blocks) == 2
    assert all("Гарантия" not in b["text"] for b in new_blocks)


def test_apply_remove_section_not_found():
    blocks = [_p("Первый пункт")]
    new_blocks, removed = apply_remove_section(blocks, "Несуществующий текст")
    assert removed == 0
    assert new_blocks == blocks


def test_apply_remove_section_case_insensitive():
    blocks = [_p("ГАРАНТИЯ на товар")]
    new_blocks, removed = apply_remove_section(blocks, "гарантия")
    assert removed == 1
    assert new_blocks == []


# ---------- parse_change_field_command ----------

def test_parse_change_field_command_basic():
    result = parse_change_field_command("измени сумму на 200000 тенге")
    assert result == ("сумму", "200000 тенге")


def test_parse_change_field_command_поменяй_synonym():
    result = parse_change_field_command("поменяй дату на 20.08.2026")
    assert result == ("дату", "20.08.2026")


def test_parse_change_field_command_исправь_synonym():
    result = parse_change_field_command("исправь заказчика на Иван Иванов")
    assert result == ("заказчика", "Иван Иванов")


def test_parse_change_field_command_no_match_returns_none():
    assert parse_change_field_command("сделай документ покороче") is None


# ---------- find_target_field ----------

def test_find_target_field_direct_label_match():
    field_def = find_target_field(TEMPLATE_SCHEMA, "заказчика")
    assert field_def is not None
    assert field_def["key"] == "customer"


def test_find_target_field_money_category_match():
    field_def = find_target_field(TEMPLATE_SCHEMA, "сумму")
    assert field_def is not None
    assert field_def["key"] == "price"


def test_find_target_field_date_category_match():
    field_def = find_target_field(TEMPLATE_SCHEMA, "дату")
    assert field_def is not None
    assert field_def["key"] == "date"


def test_find_target_field_duration_category_match():
    field_def = find_target_field(TEMPLATE_SCHEMA, "срок")
    assert field_def is not None
    assert field_def["key"] == "term"


def test_find_target_field_no_match_returns_none():
    field_def = find_target_field(TEMPLATE_SCHEMA, "совершенно постороннее слово")
    assert field_def is None
