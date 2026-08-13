"""
Централизованная конфигурация CodeNexa System backend.

Все секреты читаются ТОЛЬКО из переменных окружения.
Ничего секретное здесь не хардкодится и не коммитится.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- База данных (используется существующий Supabase Postgres) ---
    database_url: str = ""

    # --- Telegram ---
    telegram_bot_token: str = ""

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- Auth / JWT (для короткоживущих сессионных токенов, см. migrations/0001) ---
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12  # 12 часов

    # --- Supabase (если нужен прямой REST/Storage доступ) ---
    supabase_url: str = "https://vlpgdiivliozzhacymaw.supabase.co"
    supabase_service_role_key: str = ""  # ТОЛЬКО backend, никогда не в frontend

    # --- Прочее ---
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
