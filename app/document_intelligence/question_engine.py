"""
Question engine — slot filling без LLM: по fields_schema шаблона и уже
известным значениям определяет следующий незаполненный обязательный
вопрос. Не спрашивает то, что уже известно (п.7 промпта).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.document_intelligence.entities import extract_entities


@dataclass
class NextQuestion:
    field_key: str | None
    field_label: str | None
    all_required_filled: bool


def next_missing_field(fields_schema: list[dict], known_values: dict[str, str]) -> NextQuestion:
    for field_def in fields_schema:
        if not field_def.get("required"):
            continue
        key = field_def["key"]
        if not str(known_values.get(key, "")).strip():
            return NextQuestion(field_key=key, field_label=field_def.get("label", key), all_required_filled=False)
    return NextQuestion(field_key=None, field_label=None, all_required_filled=True)


def apply_free_text_answer(fields_schema: list[dict], known_values: dict[str, str], user_text: str, target_field_key: str | None) -> dict[str, str]:
    """
    Пользователь мог ответить на конкретный вопрос ("Иван Иванов") ИЛИ
    сразу дать несколько значений одним сообщением ("150000 тенге на
    3 месяца"). Стратегия:
    1. Если задавался конкретный вопрос (target_field_key), СНАЧАЛА
       пробуем понять: похож ли ответ на ожидаемый тип этого поля
       (деньги/срок/дата) — если да, заполняем именно его. Если нет —
       весь текст целиком идёт как значение именно этого поля (даже
       если в нём случайно нашлась дата/сумма — пользователь отвечал
       на конкретный вопрос, а не диктовал произвольные данные).
    2. Только для полей БЕЗ активного вопроса (например, самое первое
       сообщение целиком) — сопоставляем найденные сущности с любыми
       ещё незаполненными подходящими полями.
    """
    updated = dict(known_values)
    entities = extract_entities(user_text)

    def field_wants(field_def: dict, hints: list[str]) -> bool:
        key = field_def["key"].lower()
        label = field_def.get("label", "").lower()
        return any(h in key or h in label for h in hints)

    if target_field_key:
        target_def = next((f for f in fields_schema if f["key"] == target_field_key), None)
        if target_def:
            is_money_field = field_wants(target_def, ["price", "сумм", "стоимост", "amount"])
            is_duration_field = field_wants(target_def, ["term", "срок", "duration"])
            is_date_field = target_def.get("type") == "date" or "дат" in target_def.get("label", "").lower()

            if is_money_field and entities.money:
                m = entities.money[0]
                updated[target_field_key] = f"{int(m['amount'])} {m['currency'] or ''}".strip()
            elif is_duration_field and entities.durations:
                d = entities.durations[0]
                unit_ru = {"months": "месяцев", "days": "дней", "weeks": "недель", "years": "лет", "business_days": "рабочих дней"}[d["unit"]]
                updated[target_field_key] = f"{d['value']} {unit_ru}"
            elif is_date_field and entities.dates:
                updated[target_field_key] = entities.dates[0]["iso"]
            else:
                # Отвечали на конкретный вопрос обычным текстом — берём как есть,
                # не пытаемся "угадать" другое поле по случайно найденным сущностям.
                updated[target_field_key] = user_text.strip()
        else:
            updated[target_field_key] = user_text.strip()
        return updated

    # Без активного вопроса (первое сообщение целиком) — сопоставляем
    # найденные сущности с ещё незаполненными подходящими полями.
    if entities.money:
        for field_def in fields_schema:
            key = field_def["key"]
            if updated.get(key):
                continue
            if field_wants(field_def, ["price", "сумм", "стоимост", "amount"]):
                m = entities.money[0]
                updated[key] = f"{int(m['amount'])} {m['currency'] or ''}".strip()
                break

    if entities.durations:
        for field_def in fields_schema:
            key = field_def["key"]
            if updated.get(key):
                continue
            if field_wants(field_def, ["term", "срок", "duration"]):
                d = entities.durations[0]
                unit_ru = {"months": "месяцев", "days": "дней", "weeks": "недель", "years": "лет", "business_days": "рабочих дней"}[d["unit"]]
                updated[key] = f"{d['value']} {unit_ru}"
                break

    if entities.dates:
        for field_def in fields_schema:
            key = field_def["key"]
            if updated.get(key):
                continue
            if field_def.get("type") == "date" or "дат" in field_def.get("label", "").lower():
                updated[key] = entities.dates[0]["iso"]
                break

    return updated
