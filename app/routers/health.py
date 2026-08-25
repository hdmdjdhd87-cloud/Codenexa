from fastapi import APIRouter, Response, status

from app.database import ping

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Не зависит от внешних сервисов — просто подтверждает, что процесс жив."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict:
    """
    Проверяет реальное подключение к базе данных.

    railway.json указывает healthcheckPath на именно этот эндпоинт
    (F-011 из аудита 22.08.2026), а не на /health — идея в том, чтобы
    Railway обнаруживал ситуацию "процесс жив, но не может обслуживать
    реальные запросы" (БД недоступна) и реагировал (restart/не
    маршрутизировать трафик на этот инстанс во время rolling deploy).

    ВАЖНО: до этого исправления эндпоинт всегда отвечал HTTP 200
    независимо от db_ok, передавая деградацию только в JSON-теле —
    healthcheck-механизмы (включая Railway) обычно смотрят на HTTP-код
    ответа, а не разбирают тело, так что переключение healthcheckPath
    на /ready было чисто косметическим без этого фикса: реальный сбой
    БД никогда бы не привёл к перезапуску/выводу инстанса из ротации.
    """
    db_ok = await ping()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
