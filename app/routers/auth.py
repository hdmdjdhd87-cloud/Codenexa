from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.middleware import get_current_user_id
from app.auth.session import create_session_token
from app.auth.telegram import (
    ExpiredInitDataError,
    InvalidSignatureError,
    MalformedInitDataError,
    TelegramAuthError,
    validate_init_data,
)
from app.config import get_settings
from app.repositories.user_repository import get_or_create_user, get_user_by_id
from app.repositories.notification_repository import create_notification
from app.utils.errors import api_error
from fastapi import status

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/telegram", response_model=AuthResponse)
async def auth_telegram(payload: TelegramAuthRequest) -> AuthResponse:
    settings = get_settings()
    try:
        validated = validate_init_data(payload.init_data, settings.telegram_bot_token)
    except InvalidSignatureError as exc:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED, "INVALID_SIGNATURE", "Подпись Telegram не подтверждена."
        ) from exc
    except ExpiredInitDataError as exc:
        raise api_error(
            status.HTTP_401_UNAUTHORIZED, "INIT_DATA_EXPIRED", "Сессия Telegram устарела. Откройте приложение заново."
        ) from exc
    except MalformedInitDataError as exc:
        raise api_error(
            status.HTTP_400_BAD_REQUEST, "MALFORMED_INIT_DATA", "Некорректные данные авторизации Telegram."
        ) from exc
    except TelegramAuthError as exc:
        raise api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "AUTH_MISCONFIGURED", "Ошибка конфигурации авторизации."
        ) from exc

    user = await get_or_create_user(validated.user)
    if user.pop("is_new_user", False):
        # Единственное системное уведомление, которое реально создаётся
        # backend-событием (не fake data) — приветствие при первом входе.
        await create_notification(
            user["id"],
            "system",
            "Добро пожаловать в CodeNexa",
            "Все инструменты CodeNexa теперь доступны в одном месте.",
        )
    token = create_session_token(str(user["id"]))
    return AuthResponse(token=token, user=user)


@router.get("/me")
async def auth_me(user_id: str = Depends(get_current_user_id)) -> dict:
    user = await get_user_by_id(user_id)
    if not user:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")
    return user
