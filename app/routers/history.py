from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.middleware import get_current_user_id
from app.repositories.history_repository import list_history

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
async def get_history(
    page: int = Query(default=1, ge=1),
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    return await list_history(user_id, page=page)
