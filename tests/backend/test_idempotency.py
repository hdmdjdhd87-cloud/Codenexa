import datetime
import uuid

import pytest

from app.repositories.idempotency import _json_safe, compute_request_hash, with_idempotency


# ---------- compute_request_hash ----------

def test_compute_request_hash_is_deterministic():
    h1 = compute_request_hash("doc-1", "v-2")
    h2 = compute_request_hash("doc-1", "v-2")
    assert h1 == h2


def test_compute_request_hash_differs_for_different_params():
    h1 = compute_request_hash("doc-1", "v-2")
    h2 = compute_request_hash("doc-1", "v-3")
    assert h1 != h2


def test_compute_request_hash_differs_for_different_order():
    # порядок значим — это защита от переиспользования ключа с другими
    # (пусть и теми же по набору) параметрами
    h1 = compute_request_hash("a", "b")
    h2 = compute_request_hash("b", "a")
    assert h1 != h2


def test_compute_request_hash_handles_dict_payload():
    h = compute_request_hash("tpl-1", "Договор", {"customer": "Иванов", "price": "100000"})
    assert isinstance(h, str)
    assert len(h) == 64  # sha256 hex digest


def test_compute_request_hash_sensitive_to_dict_contents():
    h1 = compute_request_hash("tpl-1", "Договор", {"customer": "Иванов"})
    h2 = compute_request_hash("tpl-1", "Договор", {"customer": "Петров"})
    assert h1 != h2


# ---------- _json_safe ----------

def test_json_safe_converts_uuid_to_string():
    value = {"id": uuid.UUID("12345678-1234-5678-1234-567812345678")}
    result = _json_safe(value)
    assert result["id"] == "12345678-1234-5678-1234-567812345678"
    assert isinstance(result["id"], str)


def test_json_safe_converts_datetime_to_iso_string():
    value = {"created_at": datetime.datetime(2026, 8, 22, 12, 30, 0)}
    result = _json_safe(value)
    assert result["created_at"] == "2026-08-22T12:30:00"


def test_json_safe_converts_date_to_iso_string():
    value = {"date": datetime.date(2026, 8, 22)}
    result = _json_safe(value)
    assert result["date"] == "2026-08-22"


def test_json_safe_recurses_into_nested_lists_and_dicts():
    value = {
        "documents": [
            {"id": uuid.UUID("12345678-1234-5678-1234-567812345678"), "title": "Договор"},
            {"id": uuid.UUID("87654321-4321-8765-4321-876543218765"), "title": "Расписка"},
        ]
    }
    result = _json_safe(value)
    assert all(isinstance(d["id"], str) for d in result["documents"])
    assert result["documents"][0]["title"] == "Договор"


def test_json_safe_leaves_json_native_values_untouched():
    value = {"title": "Договор №1", "count": 3, "active": True, "note": None}
    assert _json_safe(value) == value


# ---------- with_idempotency: no key -> passthrough, no DB touched ----------

@pytest.mark.asyncio
async def test_with_idempotency_without_key_calls_work_fn_directly_without_db():
    calls = []

    async def work():
        calls.append(1)
        return {"ok": True}

    # idempotency_key=None -> должен просто вызвать work_fn и не пытаться
    # обратиться к БД вообще (иначе тест упал бы без подключения к Postgres)
    result = await with_idempotency("user-1", "create_document", None, work)
    assert result == {"ok": True}
    assert calls == [1]


@pytest.mark.asyncio
async def test_with_idempotency_without_key_calls_work_fn_every_time():
    calls = []

    async def work():
        calls.append(1)
        return {"call": len(calls)}

    first = await with_idempotency("user-1", "create_document", None, work)
    second = await with_idempotency("user-1", "create_document", None, work)
    # без ключа защиты нет — это ожидаемо и задокументировано в модуле
    assert first != second
    assert len(calls) == 2


# ---------- NOT VERIFIED (требует реальный Postgres) ----------
#
# Честно, по требованию production-аудита (22.08.2026): следующие
# сценарии из state machine (_claim в idempotency.py) НЕ покрыты
# юнит-тестами в этом файле, потому что они требуют реальных SQL-эффектов
# (ON CONFLICT, FOR UPDATE, транзакции, now()/lease) — их нельзя честно
# проверить без подключения к Postgres:
#
#   - два конкурентных запроса с одним ключом: только один получает
#     'claimed', второй — 409 REQUEST_IN_PROGRESS
#   - work_fn() бросает исключение -> состояние становится 'failed',
#     повторный запрос с тем же ключом может попробовать снова (а не
#     залипает в 409 навсегда — это и есть исправление SEC-003/F-003)
#   - лиз истёк (процесс убит посреди work_fn) -> следующий запрос
#     перехватывает работу заново
#   - одинаковый ключ, другой request_hash -> 422 IDEMPOTENCY_KEY_REUSED
#   - state='completed' -> response_body возвращается БЕЗ повторного
#     вызова work_fn
#
# Эти сценарии нужно проверить integration-тестами против реального
# Postgres (например тестовая БД в CI) — см. migrations/0009 и
# MANUAL_TODO.md.
