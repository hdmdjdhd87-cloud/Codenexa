from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.middleware import get_current_user_id
from app.repositories.notification_repository import list_notifications, mark_all_read, mark_read

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await list_notifications(user_id)


@router.post("/{notification_id}/read")
async def read_notification(notification_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    await mark_read(user_id, notification_id)
    return {"status": "ok"}


@router.post("/read-all")
async def read_all_notifications(user_id: str = Depends(get_current_user_id)) -> dict:
    await mark_all_read(user_id)
    return {"status": "ok"}
