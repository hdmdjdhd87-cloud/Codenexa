"""
FastAPI dependency: current_user_id.

Все защищённые роуты подключают эту зависимость и получают user_id,
уже провалидированный по подписанному сессионному токену. Ни один
роут не должен принимать user_id напрямую из query/path параметров
как источник авторизации (см. п.7 и п.33 спецификации — IDOR).

С P0-10 (admin RBAC, аудит 22.08.2026) сюда же добавлена проверка
is_blocked/sessions_valid_from — иначе "заблокировать пользователя"
и "отозвать все сессии" из админки были бы косметическими действиями,
не влияющими на уже выданный JWT (токены сами по себе stateless и
живут до истечения exp вне зависимости от действий админа). Да, это
добавляет один DB-запрос на каждый авторизованный запрос — сознательный
trade-off, т.к. без него у этих admin-действий нет реального эффекта.
Fail-CLOSED при недоступности БД (503), а не fail-open: это
security-проверка, а не вспомогательный механизм вроде rate limiting.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.auth.session import SessionTokenError, verify_session_token_full
from app.database import get_pool


async def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Требуется авторизация."}},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        user_id, issued_at = verify_session_token_full(token)
    except SessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "SESSION_INVALID", "message": "Сессия недействительна или истекла."}},
        ) from exc

    pool = get_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "DATABASE_UNAVAILABLE", "message": "База данных временно недоступна."}},
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select is_blocked, extract(epoch from sessions_valid_from)::bigint as valid_from_ts from nexa_users where id = $1",
            user_id,
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "SESSION_INVALID", "message": "Сессия недействительна или истекла."}},
        )
    if row["is_blocked"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_BLOCKED", "message": "Аккаунт заблокирован."}},
        )
    if issued_at < row["valid_from_ts"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "SESSION_REVOKED", "message": "Сессия отозвана. Войдите заново."}},
        )

    return user_id
