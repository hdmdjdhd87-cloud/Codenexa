import datetime
import uuid

import pytest

from app.repositories.idempotency import _json_safe, with_idempotency


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
