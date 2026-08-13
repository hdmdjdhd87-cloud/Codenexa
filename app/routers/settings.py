from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.middleware import get_current_user_id
from app.repositories.settings_repository import get_settings_for_user, update_settings_for_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    language: str | None = None
    theme: str | None = None
    haptic_feedback: bool | None = None
    notifications_enabled: bool | None = None


@router.get("")
async def get_settings_route(user_id: str = Depends(get_current_user_id)) -> dict:
    return await get_settings_for_user(user_id)


@router.patch("")
async def patch_settings_route(payload: SettingsPatch, user_id: str = Depends(get_current_user_id)) -> dict:
    return await update_settings_for_user(user_id, payload.model_dump(exclude_unset=True))
