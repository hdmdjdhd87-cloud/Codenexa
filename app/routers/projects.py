from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.middleware import get_current_user_id
from app.repositories.project_repository import list_projects

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
async def get_projects(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await list_projects(user_id)
