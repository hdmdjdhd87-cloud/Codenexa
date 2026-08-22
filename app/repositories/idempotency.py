"""
Идемпотентность мутирующих запросов (п.7 промпта) — защита от двойного
клика/повторной отправки на уровне БД, а не только disabled-состоянием
кнопки на фронтенде (то же требование, что уже сформулировано для
/chat в app/repositories/conversation_repository.py, здесь — общий
механизм для остальных мутирующих эндпоинтов).

Схема: атомарный INSERT ... ON CONFLICT DO NOTHING "застолбляет"
идемпотентный ключ (уникальность user_id+scope+key на уровне БД —
единственная гарантия, которая держится и при истинно параллельных
запросах, не только при разнесённых по времени). Если застолбить
получилось — выполняем работу и дописываем response_body в ту же
строку. Если не получилось (ключ уже существует):
  - response_body уже заполнен -> предыдущий запрос успел завершиться,
    возвращаем ТОТ ЖЕ результат, не выполняя работу повторно;
  - response_body ещё null -> редкий случай истинно одновременных
    запросов (первый ещё не дописал результат) — честно сообщаем,
    что запрос уже обрабатывается, вместо того чтобы тихо создать
    дубликат или тихо ничего не вернуть.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Awaitable, Callable

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


def _json_safe(value):
    """asyncpg-кодек jsonb использует голый json.dumps без default=,
    а результаты repo-функций часто содержат uuid.UUID/datetime (из
    asyncpg Record) — приводим их к строкам рекурсивно перед записью,
    иначе сохранение ответа в response_body падает с TypeError."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


class IdempotencyInProgress(Exception):
    """Тот же idempotency_key уже обрабатывается другим запросом прямо сейчас."""


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def with_idempotency(
    user_id: str, scope: str, idempotency_key: str | None, work_fn: Callable[[], Awaitable[dict]]
) -> dict:
    """
    work_fn() -> должен вернуть JSON-сериализуемый dict (тот же объект,
    что отдаётся клиенту как HTTP-ответ).

    Без idempotency_key (старые клиенты/тесты, которые его не передают)
    защита просто не применяется — обратная совместимость важнее, чем
    ломать существующие вызовы.
    """
    if not idempotency_key:
        return await work_fn()

    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        claimed = await conn.fetchrow(
            """
            insert into nexa_docs_idempotency_keys (user_id, scope, idempotency_key)
            values ($1, $2, $3)
            on conflict (user_id, scope, idempotency_key) do nothing
            returning id
            """,
            user_id,
            scope,
            idempotency_key,
        )

        if not claimed:
            existing = await conn.fetchrow(
                "select response_body from nexa_docs_idempotency_keys where user_id = $1 and scope = $2 and idempotency_key = $3",
                user_id,
                scope,
                idempotency_key,
            )
            if existing and existing["response_body"] is not None:
                return existing["response_body"]
            raise api_error(
                status.HTTP_409_CONFLICT,
                "REQUEST_IN_PROGRESS",
                "Такой же запрос уже обрабатывается — подождите и не отправляйте повторно.",
            )

        result = await work_fn()

        await conn.execute(
            "update nexa_docs_idempotency_keys set response_body = $2 where id = $1",
            claimed["id"],
            _json_safe(result),
        )
        return result
