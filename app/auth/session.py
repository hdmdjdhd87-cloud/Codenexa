"""
Сессионные токены CodeNexa System.

После успешной проверки Telegram initData (app/auth/telegram.py) backend
выдаёт короткоживущий подписанный JWT, привязанный к nexa_users.id.
Frontend хранит его и передаёт в заголовке Authorization для всех
последующих запросов. Мы намеренно НЕ доверяем telegram_user_id,
присланному отдельно от initData (см. п.7 спецификации) — только
идентификатору из уже провалидированного и подписанного токена.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings


class SessionTokenError(Exception):
    pass


def create_session_token(user_id: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise SessionTokenError("JWT_SECRET не сконфигурирован на сервере")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_session_token(token: str) -> str:
    """Возвращает user_id (nexa_users.id) из валидного токена или кидает SessionTokenError."""
    return verify_session_token_full(token)[0]


def verify_session_token_full(token: str) -> tuple[str, int]:
    """То же самое, но дополнительно возвращает iat (issued-at, unix ts) —
    нужен для проверки session-revocation (P0-10 из аудита 22.08.2026):
    admin может "отозвать все сессии" пользователя, проставив
    nexa_users.sessions_valid_from = now(); токены, выпущенные раньше
    этой отметки, перестают приниматься. Один decode вместо двух —
    verify_session_token() выше просто берёт [0] из этого же результата."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise SessionTokenError("JWT_SECRET не сконфигурирован на сервере")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise SessionTokenError(f"Невалидный или истёкший токен сессии: {exc}") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise SessionTokenError("В токене отсутствует sub (user_id)")
    issued_at = payload.get("iat")
    if issued_at is None:
        raise SessionTokenError("В токене отсутствует iat")
    return user_id, int(issued_at)
