"""
Тиры rate limiting (P0-09, production-аудит 22.08.2026) — без Redis,
см. миграцию 0011 и rate_limit_middleware.py в этом же пакете.

Вынесено в отдельный файл от самого middleware специально: сопоставление
пути с тиром — чистая функция без I/O, тестируется без ASGI/БД. Значения
лимитов — стартовые, консервативно-щедрые (аудит сам отмечает, что
реальная нагрузка не измерена — "масштаб не доказан"); при появлении
метрик стоит пересмотреть по фактическим p95/паттернам использования.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitTier:
    scope: str
    limit: int
    window_seconds: int
    identity_kind: str  # "user_or_ip" | "ip_only"


# Порядок важен: первое совпадение побеждает — от самого специфичного
# к самому общему. match_kind: "prefix" (path.startswith(pattern)) или
# "contains" (pattern in path) — export-эндпоинты (.../export/docx,
# .../export/pdf) не имеют общего префикса с другими /documents/{id}/...
# маршрутами, поэтому им нужен "contains", а не "prefix".
_TIERS: list[tuple[str, str, str, RateLimitTier]] = [
    # (method_prefix, match_kind, pattern, tier) — method_prefix "" значит любой метод
    ("", "prefix", "/api/v1/auth", RateLimitTier("auth", limit=20, window_seconds=60, identity_kind="ip_only")),
    ("", "prefix", "/api/v1/aidocs/ocr", RateLimitTier("ocr", limit=10, window_seconds=60, identity_kind="user_or_ip")),
    ("", "prefix", "/api/v1/aidocs/documents/import", RateLimitTier("ocr", limit=10, window_seconds=60, identity_kind="user_or_ip")),
    ("GET", "contains", "/export/", RateLimitTier("export", limit=30, window_seconds=60, identity_kind="user_or_ip")),
    ("", "prefix", "/api/v1/aidocs/shared", RateLimitTier("public_share", limit=60, window_seconds=60, identity_kind="ip_only")),
    ("GET", "prefix", "/api/v1/aidocs", RateLimitTier("read", limit=180, window_seconds=60, identity_kind="user_or_ip")),
    ("", "prefix", "/api/v1/aidocs", RateLimitTier("mutation", limit=60, window_seconds=60, identity_kind="user_or_ip")),
    ("", "prefix", "/api/v1", RateLimitTier("general", limit=120, window_seconds=60, identity_kind="user_or_ip")),
]

# Эндпоинты, которые НЕ ограничиваем в принципе — healthcheck'и опрашиваются
# инфраструктурой (Railway) часто и намеренно, это не пользовательский трафик.
_EXEMPT_PATHS = {"/health", "/ready"}


def resolve_tier(method: str, path: str) -> RateLimitTier | None:
    """None означает "не лимитировать" — например статика, healthcheck,
    или путь вне /api/* (сюда backend вообще ничего больше не обслуживает,
    см. app/server.py, но на всякий случай явная защита от лишнего
    лимитирования того, чего нет)."""
    if path in _EXEMPT_PATHS:
        return None

    method_upper = method.upper()
    for method_prefix, match_kind, pattern, tier in _TIERS:
        if method_prefix and method_upper != method_prefix:
            continue
        matched = path.startswith(pattern) if match_kind == "prefix" else pattern in path
        if matched:
            return tier

    return None
