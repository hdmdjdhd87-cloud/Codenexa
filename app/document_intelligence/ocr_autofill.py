"""
Автозаполнение полей формы из текста, распознанного OCR (п.5 промпта).

Раньше OCR (Tesseract) отдавал только сырой текст, а перенос в поля
формы был полностью ручным. Этот модуль честно закрывает конкретный
пробел — прогоняет распознанный текст через extract_entities() и
сопоставляет найденные сущности (деньги/даты/сроки/телефон/email) с
полями шаблона, чтобы предложить автозаполнение.

Специально НЕ пытается распознать произвольные текстовые поля вроде
"ФИО заказчика" — extract_entities() не извлекает имена собственные
(это потребовало бы NER/LLM, а не regex), и подсовывать туда
случайный обрывок OCR-текста было бы нечестной догадкой, а не
автозаполнением. Пользователь сам переносит такие поля — как и
раньше, но теперь только те, что действительно нельзя разобрать
надёжно, а не вообще всё.
"""
from __future__ import annotations

from app.document_intelligence.entities import extract_entities
from app.document_intelligence.question_engine import apply_free_text_answer

PHONE_FIELD_HINTS = ["phone", "телефон", "тел."]
EMAIL_FIELD_HINTS = ["email", "e-mail", "почта", "mail"]


def _field_wants(field_def: dict, hints: list[str]) -> bool:
    haystack = f'{field_def.get("key", "")} {field_def.get("label", "")}'.lower()
    return any(h in haystack for h in hints)


def suggest_field_values(fields_schema: list[dict], ocr_text: str) -> dict[str, str]:
    """
    Возвращает {field_key: предложенное_значение} только для полей, где
    сущность была найдена с высокой уверенностью (сумма/дата/срок —
    через уже протестированный question_engine.apply_free_text_answer;
    телефон/email — по регэкспам entities.py). Поля не в результате —
    честно оставлены для ручного заполнения пользователем.
    """
    if not ocr_text or not ocr_text.strip():
        return {}

    # apply_free_text_answer в режиме "без активного вопроса" (target=None)
    # уже делает ровно то, что нужно: сканирует ВСЕ поля и сопоставляет
    # первую подходящую сущность каждой категории (деньги/срок/дата) с
    # первым ещё незаполненным полем такой же категории.
    suggested = apply_free_text_answer(fields_schema, {}, ocr_text, None)

    entities = extract_entities(ocr_text)

    if entities.phones:
        for field_def in fields_schema:
            key = field_def["key"]
            if suggested.get(key):
                continue
            if _field_wants(field_def, PHONE_FIELD_HINTS):
                suggested[key] = entities.phones[0]
                break

    if entities.emails:
        for field_def in fields_schema:
            key = field_def["key"]
            if suggested.get(key):
                continue
            if _field_wants(field_def, EMAIL_FIELD_HINTS):
                suggested[key] = entities.emails[0]
                break

    return suggested
