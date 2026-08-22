from app.document_engine.version_diff import diff_content_blocks, diff_result_to_dict


def _p(text: str, block_type: str = "paragraph") -> dict:
    return {"type": block_type, "text": text}


# ---------- basic ops ----------

def test_identical_blocks_are_all_unchanged():
    blocks = [_p("Договор №1"), _p("Заказчик: Иванов")]
    result = diff_content_blocks(blocks, list(blocks))
    assert result.unchanged_count == 2
    assert result.added_count == 0
    assert result.removed_count == 0
    assert result.changed_count == 0
    assert all(b.op == "unchanged" for b in result.blocks)


def test_appended_block_is_added():
    old = [_p("Заказчик: Иванов")]
    new = [_p("Заказчик: Иванов"), _p("Срок: 30 дней")]
    result = diff_content_blocks(old, new)
    assert result.added_count == 1
    assert result.unchanged_count == 1
    added = [b for b in result.blocks if b.op == "added"][0]
    assert added.new_text == "Срок: 30 дней"
    assert added.old_text is None


def test_removed_block_is_removed():
    old = [_p("Заказчик: Иванов"), _p("Срок: 30 дней")]
    new = [_p("Заказчик: Иванов")]
    result = diff_content_blocks(old, new)
    assert result.removed_count == 1
    removed = [b for b in result.blocks if b.op == "removed"][0]
    assert removed.old_text == "Срок: 30 дней"
    assert removed.new_text is None


def test_same_position_text_edit_is_changed_not_add_remove():
    old = [_p("Стоимость: 100000 тенге")]
    new = [_p("Стоимость: 150000 тенге")]
    result = diff_content_blocks(old, new)
    assert result.changed_count == 1
    assert result.added_count == 0
    assert result.removed_count == 0
    changed = result.blocks[0]
    assert changed.op == "changed"
    assert changed.old_text == "Стоимость: 100000 тенге"
    assert changed.new_text == "Стоимость: 150000 тенге"


def test_changed_block_has_word_level_diff():
    old = [_p("Стоимость: 100000 тенге")]
    new = [_p("Стоимость: 150000 тенге")]
    result = diff_content_blocks(old, new)
    word_diff = result.blocks[0].word_diff
    deletions = [p.text for p in word_diff if p.op == "delete"]
    insertions = [p.text for p in word_diff if p.op == "insert"]
    assert "100000" in deletions
    assert "150000" in insertions
    # неизменная часть должна остаться как equal, не потеряться
    equal_text = " ".join(p.text for p in word_diff if p.op == "equal")
    assert "Стоимость:" in equal_text


def test_mixed_add_remove_and_unchanged():
    old = [_p("Заголовок", "heading"), _p("Старый пункт"), _p("Подпись", "signature_line")]
    new = [_p("Заголовок", "heading"), _p("Новый пункт"), _p("Подпись", "signature_line")]
    result = diff_content_blocks(old, new)
    assert result.unchanged_count == 2  # heading + signature_line
    assert result.changed_count == 1  # "Старый пункт" -> "Новый пункт"


def test_empty_old_blocks_all_added():
    result = diff_content_blocks([], [_p("Первый пункт")])
    assert result.added_count == 1
    assert result.removed_count == 0


def test_empty_new_blocks_all_removed():
    result = diff_content_blocks([_p("Первый пункт")], [])
    assert result.removed_count == 1
    assert result.added_count == 0


def test_no_changes_between_empty_lists():
    result = diff_content_blocks([], [])
    assert result.added_count == 0
    assert result.removed_count == 0
    assert result.changed_count == 0
    assert result.unchanged_count == 0
    assert result.blocks == []


def test_block_type_change_counts_as_changed_when_same_position():
    old = [_p("Итого", "paragraph")]
    new = [_p("Итого", "heading")]
    result = diff_content_blocks(old, new)
    # текст одинаковый, но тип другой -> ключ (type, text) отличается,
    # блок в той же позиции без пары считается changed (не unchanged)
    assert result.changed_count == 1
    assert result.blocks[0].block_type == "heading"


# ---------- serialization ----------

def test_diff_result_to_dict_shape():
    old = [_p("A"), _p("B")]
    new = [_p("A"), _p("C")]
    result = diff_content_blocks(old, new)
    payload = diff_result_to_dict(result)
    assert set(payload.keys()) == {"summary", "blocks"}
    assert payload["summary"] == {"added": 0, "removed": 0, "changed": 1, "unchanged": 1}
    assert all("op" in b and "word_diff" in b for b in payload["blocks"])


def test_reordering_all_blocks_is_reported_not_silently_ignored():
    old = [_p("Первый"), _p("Второй")]
    new = [_p("Второй"), _p("Первый")]
    result = diff_content_blocks(old, new)
    # Реальная перестановка должна быть видна в diff (не 0 изменений),
    # даже если итоговый набор блоков совпадает по содержимому.
    assert result.added_count > 0 or result.removed_count > 0 or result.changed_count > 0
