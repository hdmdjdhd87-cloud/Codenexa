"""
Rule-based операции редактирования УЖЕ СОЗДАННОГО документа (п.1
промпта). До этого момента интенты EDIT_DOCUMENT/CHANGE_FIELD
распознавались (intents.py), но нигде не применялись к content_blocks —
этот модуль закрывает разрыв.

Честно, без LLM — поддерживаются только явные, однозначно
парсящиеся команды:
  - "замени X на Y"              -> REPLACE_TEXT (буквальная подстрока)
  - "добавь пункт/раздел/абзац: TEXT" -> ADD_SECTION (новый блок в конец)
  - "убери/удали пункт/раздел/абзац: TEXT" -> REMOVE_SECTION (блок, содержащий TEXT)
  - "измени/поменяй/исправь <поле> на <значение>" -> CHANGE_FIELD
    (обновляет field_values и просит перегенерировать content_blocks
    через fill_template — см. document_engine/template_fill.py)

Свободное "перепиши документ покороче/официальнее" НЕ поддерживается —
это требует понимания смысла текста (LLM), а не сопоставления с
образцом. Честный отказ — в agent.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REPLACE_RE = re.compile(r"замени\s+(.+?)\s+на\s+(.+)$", re.IGNORECASE | re.DOTALL)
ADD_SECTION_RE = re.compile(r"добавь\s+(?:пункт|раздел|абзац)[:\s]+(.+)$", re.IGNORECASE | re.DOTALL)
REMOVE_SECTION_RE = re.compile(r"(?:убери|удали)\s+(?:пункт|раздел|абзац)[:\s]+(.+)$", re.IGNORECASE | re.DOTALL)
CHANGE_FIELD_RE = re.compile(r"(?:измени|поменяй|исправь)\S*\s+(.+?)\s+на\s+(.+)$", re.IGNORECASE | re.DOTALL)

# Категориальные подсказки для сопоставления упомянутого пользователем
# "поля" (например "сумму") с реальным field_key/label из fields_schema
# шаблона — та же идея, что field_wants() в question_engine.py, но
# симметричная: проверяем совпадение и со стороны текста пользователя,
# и со стороны схемы поля.
FIELD_CATEGORY_HINTS: dict[str, list[str]] = {
    "money": ["price", "сумм", "стоимост", "amount", "оплат"],
    "duration": ["term", "срок", "duration"],
    "date": ["дат", "date"],
}


@dataclass
class ParsedEditCommand:
    op: str  # "replace_text" | "add_section" | "remove_section" | "unrecognized"
    old_text: str | None = None
    new_text: str | None = None


def parse_edit_command(user_text: str) -> ParsedEditCommand:
    """Разбирает команду EDIT_DOCUMENT (замени/добавь/удали). НЕ пытается
    распознать CHANGE_FIELD — для этого отдельно parse_change_field_command,
    вызывающий код (agent.py) сам решает, какой парсер использовать
    по intent."""
    text = user_text.strip()

    m = REPLACE_RE.search(text)
    if m:
        return ParsedEditCommand(op="replace_text", old_text=m.group(1).strip(), new_text=m.group(2).strip())

    m = ADD_SECTION_RE.search(text)
    if m:
        return ParsedEditCommand(op="add_section", new_text=m.group(1).strip())

    m = REMOVE_SECTION_RE.search(text)
    if m:
        return ParsedEditCommand(op="remove_section", old_text=m.group(1).strip())

    return ParsedEditCommand(op="unrecognized")


def apply_replace_text(content_blocks: list[dict], old_text: str, new_text: str) -> tuple[list[dict], int]:
    """Регистронезависимая замена подстроки во всех блоках. Возвращает
    (новые_блоки, число_замен) — 0 значит текст не найден нигде, и
    вызывающий код должен честно об этом сказать, а не молча
    вернуть документ без изменений."""
    if not old_text:
        return [dict(b) for b in content_blocks], 0

    pattern = re.compile(re.escape(old_text), re.IGNORECASE)
    result: list[dict] = []
    replaced = 0
    for block in content_blocks:
        text = block.get("text", "")
        new_block_text, count = pattern.subn(new_text, text)
        if count:
            replaced += count
            result.append({**block, "text": new_block_text})
        else:
            result.append(dict(block))
    return result, replaced


def apply_add_section(content_blocks: list[dict], text: str, block_type: str = "paragraph") -> list[dict]:
    return [*[dict(b) for b in content_blocks], {"type": block_type, "text": text}]


def apply_remove_section(content_blocks: list[dict], text_hint: str) -> tuple[list[dict], int]:
    """Удаляет блоки, чей текст содержит text_hint (регистронезависимо).
    Возвращает (новые_блоки, число_удалённых)."""
    if not text_hint:
        return [dict(b) for b in content_blocks], 0

    hint_lower = text_hint.lower()
    result: list[dict] = []
    removed = 0
    for block in content_blocks:
        if hint_lower in block.get("text", "").lower():
            removed += 1
            continue
        result.append(dict(block))
    return result, removed


def parse_change_field_command(user_text: str) -> tuple[str, str] | None:
    """Возвращает (упомянутое_поле_текстом, новое_значение_текстом) или
    None если команда не в ожидаемом формате "измени X на Y"."""
    m = CHANGE_FIELD_RE.search(user_text.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def find_target_field(fields_schema: list[dict], field_hint: str) -> dict | None:
    """Сопоставляет упомянутое пользователем поле (например "сумму") с
    полем из fields_schema. Сначала пробуем прямое совпадение слова
    label/key с текстом подсказки (для произвольных полей — "заказчик",
    "исполнитель"), затем категориальное (сумма/срок/дата — те же
    группы, что использует question_engine для типизированного
    заполнения)."""
    hint_lower = field_hint.lower()

    best: dict | None = None
    best_len = 0
    for field_def in fields_schema:
        haystack = f'{field_def.get("label", "")} {field_def.get("key", "")}'.lower()
        for word in re.split(r"\W+", haystack):
            if len(word) > 3 and word in hint_lower and len(word) > best_len:
                best, best_len = field_def, len(word)
    if best:
        return best

    for hints in FIELD_CATEGORY_HINTS.values():
        if not any(h in hint_lower for h in hints):
            continue
        for field_def in fields_schema:
            haystack = f'{field_def.get("key", "")} {field_def.get("label", "")}'.lower()
            if any(h in haystack for h in hints):
                return field_def

    return None
