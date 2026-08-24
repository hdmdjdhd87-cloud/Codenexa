"""
CodeNexa System — backend entry point.

Запуск: uvicorn app.server:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import connect, disconnect
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, favorites, health, history, modules, notifications, projects, settings as settings_router, users, aidocs, admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("codenexa")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    logger.info("CodeNexa System backend запущен")
    yield
    await disconnect()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CodeNexa System API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        RateLimitMiddleware,
    )

    # ВАЖНО: порядок add_middleware в Starlette обратный — последний
    # добавленный оборачивает предыдущие (выполняется первым на входе,
    # последним на выходе). CORS должен быть снаружи RateLimitMiddleware,
    # иначе браузер не увидит CORS-заголовков на 429-ответе от лимитера
    # и покажет невнятную CORS-ошибку вместо настоящего RATE_LIMITED.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        # F-014 (production-аудит 22.08.2026): было allow_methods=["*"]/
        # allow_headers=["*"]. Сужено до реально используемого набора —
        # проверено по всему frontend/src (apiClient.ts, aidocsService.ts):
        # методы GET/POST/PATCH/DELETE, заголовки Authorization/
        # Content-Type/Idempotency-Key. Если добавите новый заголовок на
        # фронтенде — не забудьте добавить его и сюда.
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    # Самый внешний слой (добавлен последним) — гарантирует, что security-
    # заголовки попадают буквально на ЛЮБОЙ ответ клиенту: успешный,
    # ошибку от exception_handler'а, 429 от RateLimitMiddleware, CORS
    # preflight и т.д. (раздел 4 аудита 22.08.2026: "Security headers:
    # Недостаточно — CSP, Referrer-Policy, X-Content-Type-Options, frame
    # policy").
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        # Единый формат ошибок (п.32). Если detail уже в нужном формате — используем как есть,
        # иначе оборачиваем в { "error": { code, message } } без утечки внутренних деталей.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            body = exc.detail
        else:
            body = {"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка сервера")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Внутренняя ошибка сервера."}},
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(modules.router)
    app.include_router(favorites.router)
    app.include_router(history.router)
    app.include_router(notifications.router)
    app.include_router(settings_router.router)
    app.include_router(projects.router)
    app.include_router(aidocs.router)
    app.include_router(aidocs.public_router)
    app.include_router(admin.router)

    return app


app = create_app()
