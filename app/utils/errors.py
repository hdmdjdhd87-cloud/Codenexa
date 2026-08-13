"""
Единый формат ошибок API:
  { "error": { "code": "MODULE_NOT_FOUND", "message": "Приложение не найдено." } }

Никогда не отдаём пользователю stack trace или технические детали —
только человекочитаемое сообщение на русском и стабильный код ошибки.
"""
from __future__ import annotations

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})
