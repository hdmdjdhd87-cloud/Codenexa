from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.middleware import get_current_user_id
from app.repositories.history_repository import add_history_event
from app.services.module_service import module_registry

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


@router.get("")
async def list_modules(_user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await module_registry.get_active()


@router.get("/{module_id}")
async def get_module(module_id: str, user_id: str = Depends(get_current_user_id)) -> dict:
    module = await module_registry.get(module_id)
    # Реальное событие для раздела "История" (п.22 спецификации: каждая
    # запись создаётся backend-событием, а не выдумывается на фронте).
    await add_history_event(user_id, "module_open", module_id=module["id"], metadata={"module_key": module["module_key"]})
    return module

