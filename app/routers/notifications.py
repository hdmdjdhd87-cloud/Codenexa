from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.middleware import get_current_user_id
from app.repositories.notification_repository import list_notifications, mark_all_read, mark_read

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    return await list_notifications(user_id, page=page, page_size=page_size)


@router.post("/{notification_id}/read")
async def read_notification(notification_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    await mark_read(user_id, notification_id)
    return {"status": "ok"}


@router.post("/read-all")
async def read_all_notifications(user_id: str = Depends(get_current_user_id)) -> dict:
    await mark_all_read(user_id)
    return {"status": "ok"}
