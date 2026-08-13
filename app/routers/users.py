from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.middleware import get_current_user_id
from app.repositories.user_repository import get_user_by_id
from app.utils.errors import api_error
from fastapi import status

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user_id)) -> dict:
    # Намеренно нет /users/{id} — пользователь может получить только себя.
    # Это закрывает IDOR-сценарий "GET /api/v1/users/B" из п.33 спецификации.
    user = await get_user_by_id(user_id)
    if not user:
        raise api_error(status.HTTP_404_NOT_FOUND, "USER_NOT_FOUND", "Пользователь не найден.")
    return user
