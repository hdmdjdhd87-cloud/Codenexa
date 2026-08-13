from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.middleware import get_current_user_id
from app.services.module_service import module_registry

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


@router.get("")
async def list_modules(_user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await module_registry.get_active()


@router.get("/{module_id}")
async def get_module(module_id: str, _user_id: str = Depends(get_current_user_id)) -> dict:
    return await module_registry.get(module_id)
