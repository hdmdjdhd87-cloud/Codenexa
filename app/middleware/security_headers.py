"""
Security headers middleware (аудит 22.08.2026, раздел 4 "API security —
полный checklist": "Security headers: Недостаточно — CSP,
Referrer-Policy, X-Content-Type-Options, frame policy").

Один и тот же набор заголовков подходит и JSON API (заголовки там
просто не используются браузером ни для чего, но не мешают), и
HTML-страницам share-viewer (единственное место, отдающее HTML —
app/routers/aidocs.py, только инлайн <style>, без <script> и внешних
ресурсов — см. проверку перед написанием этого файла).
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# script-src 'none': ни JSON API, ни share-viewer НЕ используют JS вообще
# (share-viewer — чистый HTML+CSS, кнопки — обычные <a href>, не onclick).
# style-src 'unsafe-inline' обязателен: share-viewer рендерит <style>
# инлайн (см. _SHARED_CSS в aidocs.py) — переезд на внешний CSS-файл не
# входил в scope этого исправления, было бы отдельным изменением.
# frame-ancestors 'none': share-ссылки не должны встраиваться в чужой
# iframe (защита от clickjacking на кнопках "Скачать PDF/DOCX").
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'none'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Дублирует frame-ancestors из CSP для браузеров, которые не
        # поддерживают CSP2 (X-Frame-Options — легаси-заголовок, но
        # безвредный дубль, а не конфликт).
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS — весь прод-трафик идёт через HTTPS (Railway/Supabase),
        # заголовок безвреден и для локальной разработки (браузер
        # применяет HSTS только к реальным HTTPS-соединениям).
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        # Отключаем автоматический доступ к чувствительным browser API,
        # которые это приложение не использует ни на бэкенде, ни на
        # фронтенде (Telegram Mini App сам управляет своими permissions).
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response
