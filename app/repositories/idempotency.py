"""
Идемпотентность мутирующих запросов (п.7 промпта; исправлено по
production-аудиту 22.08.2026, находки SEC-003/F-003/F-004) — защита от
двойного клика/повторной отправки на уровне БД, а не только
disabled-состоянием кнопки на фронтенде.

История версии 1 (см. git-историю этого файла) держала connection из
пула открытым на всё время work_fn() и не оборачивала INSERT в явную
транзакцию — при исключении внутри work_fn() "клеймённая" запись
оставалась в БД навсегда с response_body=null, и все последующие
запросы с тем же ключом получали 409 REQUEST_IN_PROGRESS бесконечно.
Аудит был прав — это подтверждённый баг, не false positive.

Версия 2 — recoverable state machine:
  pending   — работа "застолблена" и либо выполняется прямо сейчас
              (лиз ещё не истёк), либо предыдущая попытка упала без
              обновления статуса (процесс убит/крашнулся) — тогда лиз
              истекает и следующий запрос с тем же ключом может
              перехватить работу заново;
  completed — response_body гарантированно заполнен, отдаём его;
  failed    — work_fn() бросил исключение; следующий запрос с тем же
              ключом получает право попробовать снова (это НЕ
              "поломанный" ключ навсегда, а честная возможность повтора
              после транзиентной ошибки).

Соединение с БД держится только на короткие claim/finalize шаги
(F-004) — сама работа (work_fn) выполняется без удержания connection
slot из пула, что важно под нагрузкой (max_size=10 на инстанс).

request_hash (опционально) — если один и тот же Idempotency-Key
внезапно приходит с другими значимыми параметрами запроса (баг
клиента, переиспользование ключа), это отдельная ошибка 422, а не
тихая подмена результата.
"""
from __future__ import annotations

import datetime
import hashlib
import uuid
from typing import Awaitable, Callable

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status

DEFAULT_LEASE_SECONDS = 120


def compute_request_hash(*parts: object) -> str:
    """Хэш значимых параметров запроса — чтобы отличить "тот же клиент
    повторил тот же клик" от "клиент по ошибке переиспользовал ключ для
    другого запроса"."""
    raw = "\x1f".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def _claim(pool, user_id: str, scope: str, idempotency_key: str, request_hash: str | None, lease_seconds: int):
    """Возвращает ('claimed', id) если работу можно (пере)выполнить, или
    ('completed', response_body) если результат уже есть и work_fn
    вызывать не нужно. Иначе бросает api_error (409/422)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                insert into nexa_docs_idempotency_keys
                    (user_id, scope, idempotency_key, state, lease_expires_at, request_hash)
                values ($1, $2, $3, 'pending', now() + make_interval(secs => $4), $5)
                on conflict (user_id, scope, idempotency_key) do nothing
                returning id
                """,
                user_id,
                scope,
                idempotency_key,
                float(lease_seconds),
                request_hash,
            )
            if row:
                return "claimed", str(row["id"])

            # Ключ уже существует — смотрим на его состояние под блокировкой
            # строки (FOR UPDATE), чтобы конкурентные запросы с тем же
            # ключом не могли одновременно "перехватить" один и тот же
            # истёкший лиз/failed-статус.
            existing = await conn.fetchrow(
                """
                select id, state, response_body, request_hash, lease_expires_at
                from nexa_docs_idempotency_keys
                where user_id = $1 and scope = $2 and idempotency_key = $3
                for update
                """,
                user_id,
                scope,
                idempotency_key,
            )
            if not existing:
                # Не должно происходить (строки этой таблицы никогда не
                # удаляются в обычной работе), но на всякий случай — просим
                # клиента повторить, а не падаем с 500.
                raise api_error(
                    status.HTTP_409_CONFLICT, "REQUEST_IN_PROGRESS", "Повторите запрос через секунду."
                )

            if request_hash and existing["request_hash"] and existing["request_hash"] != request_hash:
                raise api_error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "IDEMPOTENCY_KEY_REUSED",
                    "Этот Idempotency-Key уже был использован для запроса с другими параметрами.",
                )

            if existing["state"] == "completed":
                return "completed", existing["response_body"]

            now = datetime.datetime.now(datetime.timezone.utc)
            lease_expires_at = existing["lease_expires_at"]
            still_leased = existing["state"] == "pending" and lease_expires_at and lease_expires_at > now

            if still_leased:
                raise api_error(
                    status.HTTP_409_CONFLICT,
                    "REQUEST_IN_PROGRESS",
                    "Такой же запрос уже обрабатывается — подождите и не отправляйте повторно.",
                )

            # state == 'failed', либо 'pending' с истёкшим лизом (предыдущая
            # попытка упала без обновления статуса — процесс убит/крашнулся) —
            # честно даём попробовать снова.
            reclaimed = await conn.fetchrow(
                """
                update nexa_docs_idempotency_keys
                set state = 'pending',
                    lease_expires_at = now() + make_interval(secs => $2),
                    response_body = null,
                    error_message = null,
                    request_hash = coalesce($3, request_hash)
                where id = $1
                returning id
                """,
                existing["id"],
                float(lease_seconds),
                request_hash,
            )
            return "claimed", str(reclaimed["id"])


async def with_idempotency(
    user_id: str,
    scope: str,
    idempotency_key: str | None,
    work_fn: Callable[[], Awaitable[dict]],
    request_hash: str | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
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
    outcome, payload = await _claim(pool, user_id, scope, idempotency_key, request_hash, lease_seconds)

    if outcome == "completed":
        return payload  # уже готовый результат, work_fn не вызывался

    claimed_id = payload

    # Соединение из шага claim уже освобождено (вышли из `async with
    # pool.acquire()` внутри _claim) — work_fn выполняется без удержания
    # connection slot из пула (F-004 из аудита).
    try:
        result = await work_fn()
    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                "update nexa_docs_idempotency_keys set state = 'failed', error_message = $2 where id = $1",
                claimed_id,
                str(exc)[:2000],
            )
        raise

    async with pool.acquire() as conn:
        await conn.execute(
            "update nexa_docs_idempotency_keys set state = 'completed', response_body = $2 where id = $1",
            claimed_id,
            _json_safe(result),
        )
    return result
