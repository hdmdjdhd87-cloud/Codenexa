"""
Централизованная конфигурация CodeNexa System backend.

Все секреты читаются ТОЛЬКО из переменных окружения.
Ничего секретное здесь не хардкодится и не коммитится.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# P0-03 из аудита 22.08.2026: "Ограничить JWT algorithm конфигом
# allowlist и fail-fast на слабых/неожиданных значениях". jose.jwt.decode
# уже вызывается с algorithms=[settings.jwt_algorithm] — ОДНИМ значением,
# не списком/wildcard, поэтому классическая atака alg-confusion
# (например RS256 vs HS256 путаница) здесь неприменима в принципе. Но
# без этой проверки ничто не мешало бы случайно выставить
# JWT_ALGORITHM=none в .env — jose приняла бы ЛЮБОЙ неподписанный токен
# как валидный. Allowlist — только симметричные HMAC-алгоритмы,
# соответствующие тому, как токен реально создаётся (общий jwt_secret,
# не пара приватный/публичный ключ).
_ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


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

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, value: str) -> str:
        if value not in _ALLOWED_JWT_ALGORITHMS:
            raise ValueError(
                f"JWT_ALGORITHM={value!r} не в допустимом списке {sorted(_ALLOWED_JWT_ALGORITHMS)}. "
                "Это fail-fast защита от случайной конфигурации вроде 'none' "
                "(приняла бы любой неподписанный токен как валидный) — см. P0-03 аудита 22.08.2026."
            )
        return value

    # --- Supabase (если нужен прямой REST/Storage доступ) ---
    # ВНИМАНИЕ: это поле сейчас НИГДЕ в коде не используется для
    # реального подключения — фактическая связь с БД идёт через
    # database_url (см. app/database.py). Значение по умолчанию было
    # обнаружено production-аудитом (22.08.2026) как устаревшее/не
    # совпадающее с реально используемым Supabase project ref — намеренно
    # оставляю поле ПУСТЫМ по умолчанию, а не подставляю какой-либо
    # project ref "по памяти" без возможности это проверить из песочницы.
    # См. SEC-002 в аудите и expected_db_project_ref ниже — реальная
    # защита от "пишем не в ту БД" реализована через сверку project ref
    # из DATABASE_URL, а не через это поле.
    supabase_url: str = ""
    supabase_service_role_key: str = ""  # ТОЛЬКО backend, никогда не в frontend

    # --- Safety-проверка при старте (SEC-002 из аудита 22.08.2026):
    # если задано, database.connect() сверяет project ref, извлечённый
    # из DATABASE_URL, с этим значением и падает при несовпадении —
    # чтобы приложение не могло молча начать работать не с той БД
    # (перепутанные production/staging окружения). Пусто по умолчанию —
    # проверка не блокирует существующие деплои, пока ops явно не
    # укажет ожидаемый ref.
    expected_db_project_ref: str = ""

    # --- AI Docs: провайдер LLM (см. app/ai/provider.py) ---
    # Пока не заполнены — AI Docs работает в fallback-режиме без
    # AI-диалога (шаблоны, DOCX/PDF генерация работают и без этого).
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Прочее ---
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
