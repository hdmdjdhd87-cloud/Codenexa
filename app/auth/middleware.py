"""
FastAPI dependency: current_user_id.

Все защищённые роуты подключают эту зависимость и получают user_id,
уже провалидированный по подписанному сессионному токену. Ни один
роут не должен принимать user_id напрямую из query/path параметров
как источник авторизации (см. п.7 и п.33 спецификации — IDOR).
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.auth.session import SessionTokenError, verify_session_token


async def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Требуется авторизация."}},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_session_token(token)
    except SessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "SESSION_INVALID", "message": "Сессия недействительна или истекла."}},
        ) from exc
