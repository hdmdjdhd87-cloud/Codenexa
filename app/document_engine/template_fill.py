"""
Заполнение шаблона значениями формы (mail-merge, без AI).

Это единственный путь создания документа, который работает прямо
сейчас без ключа LLM (п.29 спецификации — базовые функции должны
работать, даже если AI недоступен). AI-диалог (собеседование
пользователя, распознавание фото/PDF) архитектурно вынесен в
AIProvider (app/ai/provider.py) и требует настройки ключа.
"""
from __future__ import annotations

import re

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def fill_template(body_template: list[dict], field_values: dict[str, str]) -> list[dict]:
    """
    body_template: [{"type": "heading", "text": "{{subject}}"}, ...]
    Возвращает content_blocks с подставленными значениями. Пустые
    необязательные поля превращают строку в пустую (не оставляют
    "{{purpose}}" видимым пользователю).
    """
    def substitute(text: str) -> str:
        def repl(m: re.Match) -> str:
            key = m.group(1)
            return str(field_values.get(key, "") or "")
        return PLACEHOLDER_RE.sub(repl, text)

    result = []
    for block in body_template:
        block_type = block.get("type", "paragraph")
        raw_text = block.get("text", "")
        placeholder_keys = PLACEHOLDER_RE.findall(raw_text)
        text = substitute(raw_text)

        if block_type != "spacer":
            # Если в исходном тексте блока были плейсхолдеры, но ВСЕ они
            # оказались пустыми — блок целиком неинформативен (например
            # "Основание: {{reason}}" при незаполненном необязательном
            # поле), убираем его, а не показываем голую подпись поля.
            if placeholder_keys and all(not str(field_values.get(k, "") or "").strip() for k in placeholder_keys):
                continue
            if not any(ch.isalnum() for ch in text):
                continue

        result.append({"type": block_type, "text": text})
    return result


def validate_required_fields(fields_schema: list[dict], field_values: dict[str, str]) -> list[str]:
    """Возвращает список label обязательных полей, которые не заполнены."""
    missing = []
    for field in fields_schema:
        if field.get("required") and not str(field_values.get(field["key"], "")).strip():
            missing.append(field.get("label", field["key"]))
    return missing
