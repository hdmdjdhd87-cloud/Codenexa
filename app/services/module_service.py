"""
ModuleRegistry — единая точка доступа к списку модулей экосистемы.

Ключевое архитектурное правило (п.13 спецификации): нигде в Core
не должно быть `if module_key == "nexa-files"` и т.п. Любой код,
которому нужны модули, работает только через этот сервис.

Источник данных — таблица nexa_modules (registry-driven, не хардкод).
Добавление нового модуля = INSERT в nexa_modules, без изменений кода Core.
"""
from __future__ import annotations

from app.repositories.module_repository import get_module_by_id, list_active_modules
from app.utils.errors import api_error
from fastapi import status


class ModuleRegistry:
    async def get_all(self) -> list[dict]:
        return await list_active_modules()

    async def get_active(self) -> list[dict]:
        modules = await list_active_modules()
        return [m for m in modules if m["status"] == "active"]

    async def get_by_category(self, category: str) -> list[dict]:
        modules = await self.get_active()
        return [m for m in modules if m["category"] == category]

    async def get(self, module_id: str) -> dict:
        module = await get_module_by_id(module_id)
        if not module:
            raise api_error(status.HTTP_404_NOT_FOUND, "MODULE_NOT_FOUND", "Приложение не найдено.")
        return module

    async def is_enabled(self, module_id: str) -> bool:
        module = await get_module_by_id(module_id)
        return bool(module and module["status"] == "active")


module_registry = ModuleRegistry()
