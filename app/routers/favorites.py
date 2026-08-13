from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.middleware import get_current_user_id
from app.repositories.favorite_repository import add_favorite, list_favorites, remove_favorite

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])


class FavoriteRequest(BaseModel):
    module_id: str


@router.get("")
async def get_favorites(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    # user_id берётся ИСКЛЮЧИТЕЛЬНО из токена, а не из query/path — исключает IDOR.
    return await list_favorites(user_id)


@router.post("")
async def create_favorite(payload: FavoriteRequest, user_id: str = Depends(get_current_user_id)) -> dict:
    return await add_favorite(user_id, payload.module_id)


@router.delete("/{module_id}")
async def delete_favorite(module_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    await remove_favorite(user_id, module_id)
    return {"status": "ok"}
