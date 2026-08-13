from fastapi import APIRouter

from app.database import ping

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Не зависит от внешних сервисов — просто подтверждает, что процесс жив."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict:
    """Проверяет реальное подключение к базе данных."""
    db_ok = await ping()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
