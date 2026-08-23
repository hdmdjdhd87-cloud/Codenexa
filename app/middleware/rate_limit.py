"""
Rate limiting middleware (P0-09, production-аудит 22.08.2026) —
Postgres-backed fixed-window счётчик, без Redis (см. docstring
rate_limit_tiers.py про то, почему сейчас без Redis).

Fail-open по конструкции: если сама проверка лимита не удалась (БД
недоступна) — пропускаем запрос, а не блокируем весь трафик из-за
второстепенного защитного механизма. Это осознанный trade-off, не
обход security-контролей (rate limiting — defense-in-depth, а не
единственная линия защиты от IDOR/auth, которые проверяются отдельно
и не деградируют).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.session import SessionTokenError, verify_session_token
from app.database import get_pool
from app.middleware.rate_limit_tiers import resolve_tier

logger = logging.getLogger("codenexa.rate_limit")


def _client_ip(request: Request) -> str:
    """Railway (и большинство PaaS) проксирует трафик — request.client.host
    был бы IP самого прокси, а не реального клиента. X-Forwarded-For может
    содержать цепочку через запятую (client, proxy1, proxy2, ...) — берём
    первый адрес (ближайший к клиенту)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _resolve_identity(request: Request, identity_kind: str) -> str:
    if identity_kind == "ip_only":
        return f"ip:{_client_ip(request)}"

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            user_id = verify_session_token(token)
            return f"user:{user_id}"
        except SessionTokenError:
            pass  # невалидный токен — сам запрос всё равно упадёт на auth-проверке роута, тут просто fallback identity
    return f"ip:{_client_ip(request)}"


async def _check_and_increment(identity: str, scope: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """Возвращает (allowed, current_count, seconds_until_window_reset).
    Атомарно за счёт одного INSERT ... ON CONFLICT DO UPDATE — конкурентные
    запросы того же identity/scope/window сериализуются на уровне строки,
    не на уровне приложения."""
    pool = get_pool()
    if pool is None:
        # Fail-open — БД недоступна, не блокируем трафик из-за этого.
        return True, 0, window_seconds

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_rate_limit_hits (identity, scope, window_start, request_count)
            values (
                $1, $2,
                to_timestamp(floor(extract(epoch from now()) / $3) * $3),
                1
            )
            on conflict (identity, scope, window_start)
            do update set request_count = nexa_rate_limit_hits.request_count + 1
            returning request_count, window_start
            """,
            identity,
            scope,
            window_seconds,
        )

    count = row["request_count"]
    window_start = row["window_start"]
    seconds_elapsed = (datetime.now(timezone.utc) - window_start).total_seconds()
    seconds_until_reset = max(1, int(window_seconds - seconds_elapsed))
    return count <= limit, count, seconds_until_reset


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        tier = resolve_tier(request.method, request.url.path)
        if tier is None:
            return await call_next(request)

        identity = _resolve_identity(request, tier.identity_kind)

        try:
            allowed, count, retry_after = await _check_and_increment(
                identity, tier.scope, tier.limit, tier.window_seconds
            )
        except Exception:
            # Fail-open: проблема с самим rate-limiting не должна валить
            # реальный запрос пользователя. Логируем, чтобы не проглядеть
            # деградацию этого механизма молча.
            logger.exception("rate_limit check failed, failing open")
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Слишком много запросов. Повторите через {retry_after} сек.",
                    }
                },
            )

        return await call_next(request)
