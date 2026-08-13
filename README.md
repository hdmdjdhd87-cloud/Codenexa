# CodeNexa System

**CodeNexa System** — центральная система экосистемы CodeNexa: Telegram
Mini App, через которую пользователь получает доступ ко всем продуктам
CodeNexa из единой точки входа. Это не лендинг и не демо — это ядро
(Core), к которому в будущем модульно подключаются отдельные продукты
(NexaFiles, NexaPost, NexaDocs и т.д.), без переписывания самого ядра.

Русское отображаемое название: **CodeNexa**.

## Архитектура

```
Telegram → Mini App (React) → FastAPI backend → PostgreSQL (Supabase)
```

- **Frontend**: React + TypeScript + Vite + Tailwind CSS, React Query для
  data-fetching, react-router для навигации. `frontend/`.
- **Backend**: Python + FastAPI, асинхронный доступ к PostgreSQL через
  `asyncpg`. `app/`.
- **База данных**: тот же Supabase Postgres-проект, что используется
  другими продуктами CodeNexa (`vlpgdiivliozzhacymaw.supabase.co`), но
  **изолированно** — все таблицы CodeNexa System с префиксом `nexa_`.
  Старые таблицы (`services`, `bookings`, `working_hours` и т.д.)
  никогда не затрагиваются миграциями этого проекта.
- **Авторизация**: только через Telegram. Frontend получает `initData`
  из Telegram WebApp SDK и отправляет на backend; backend проверяет
  HMAC-подпись (`app/auth/telegram.py`) и выдаёт короткоживущий JWT.
  Frontend никогда сам не решает, кто пользователь.
- **Module Registry**: единая точка правды о модулях —
  таблица `nexa_modules` (backend) + `frontend/src/modules/registry.tsx`
  (frontend component registry). Подробности и инструкция по добавлению
  нового модуля — [`docs/modules.md`](docs/modules.md).

## Структура репозитория

```
app/                    — backend (FastAPI)
  server.py             — точка входа
  config.py             — конфигурация из env
  database.py           — пул подключений PostgreSQL
  auth/                 — Telegram initData validation, JWT-сессии, middleware
  routers/               — /api/v1/* эндпоинты
  services/              — бизнес-логика (Module Registry и т.д.)
  repositories/           — доступ к БД
  utils/                 — общие утилиты (единый формат ошибок)

frontend/               — frontend (React + TS + Vite)
  src/
    app/                — App.tsx, роутинг, AuthGate
    components/          — переиспользуемые UI-компоненты
    features/            — экраны Core (Home, Catalog, Favorites, ...)
    modules/             — модули экосистемы (пока только demo)
    hooks/               — React Query hooks
    services/            — тонкий слой над API
    lib/                 — apiClient, Telegram SDK wrapper, token storage
    i18n/                — локализация (по умолчанию ru-RU)
    types/               — общие TypeScript-типы
    styles/              — дизайн-токены и глобальные стили

migrations/              — SQL-миграции (только nexa_* таблицы)
tests/backend/            — pytest
docs/                     — документация, включая ручные шаги деплоя
```

## Как запустить локально

### Backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить реальными значениями
uvicorn app.server:app --reload --port 8000
```

Проверка: `curl http://localhost:8000/health` → `{"status":"ok"}`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Откроется на `http://localhost:5173`. Полноценный `window.Telegram.WebApp`
с реальным `initData` доступен только внутри самого Telegram — в обычном
браузере `AuthGate` покажет сообщение о необходимости открыть через
Telegram (в dev-режиме это не блокирует работу — проверка активна
только в production-сборке).

## Environment variables

См. `.env.example` (backend, корень репозитория) и `frontend/.env.example`.
Полный практический чек-лист — [`docs/MANUAL_STEPS.md`](docs/MANUAL_STEPS.md)
(что нужно сделать руками в Railway/Supabase/BotFather).

**Никогда** не коммитить `.env` — только `.env.example` с пустыми
плейсхолдерами. `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`,
`JWT_SECRET`, `DATABASE_URL` — только backend, никогда не в
`VITE_*`-переменных фронтенда.

## Миграции

Файлы в `migrations/*.sql` применяются вручную через Supabase SQL Editor
(из песочницы ассистента нет сетевого доступа к `supabase.co` — см.
`docs/MANUAL_STEPS.md`). Все скрипты идемпотентны (`IF NOT EXISTS` /
`ON CONFLICT DO NOTHING`), их безопасно перезапускать.

- `0001_nexa_core.sql` — все базовые таблицы (`nexa_users`, `nexa_modules`,
  `nexa_user_modules`, `nexa_favorites`, `nexa_projects`, `nexa_history`,
  `nexa_notifications`, `nexa_settings`) + индексы + FK + триггеры.
- `0002_nexa_seed_demo_module.sql` — единственный seed: demo-модуль для
  проверки Module Registry.

## Как добавить новый модуль

Подробная инструкция: [`docs/modules.md`](docs/modules.md). Коротко:
1. Новая миграция — `INSERT` в `nexa_modules`.
2. Одна строка в `frontend/src/modules/registry.tsx`.
3. Компонент модуля в `frontend/src/modules/<module-key>/`.

## Как добавить новую категорию каталога

Категории **registry-driven**, не хардкожены в UI: значение поля
`category` в `nexa_modules` автоматически появляется как фильтр в
каталоге (`frontend/src/features/catalog/CatalogPage.tsx` строит список
категорий из реальных данных). Пустые категории просто не показываются.

## Как добавить перевод

Локализация — `frontend/src/i18n/`. Сейчас реализован только `ru-RU`
(`frontend/src/i18n/ru/index.ts`), но система рассчитана на добавление
`en`/`kk` без переписывания компонентов:

1. Создать `frontend/src/i18n/en/index.ts` с тем же набором ключей.
2. Зарегистрировать в `frontend/src/i18n/index.ts`
   (`dictionaries["en-US"] = en`).
3. Компоненты, использующие `t("...")`, менять не нужно.

## Тесты

```bash
# Backend
python3 -m pytest tests/backend -v

# Frontend
cd frontend && npm run test
```

Backend-тесты покрывают: HMAC-валидацию Telegram initData (валидная
подпись/подделанная/чужой bot token/истёкший auth_date/будущий
auth_date), health/ready без падения без БД, 401 на все защищённые
эндпоинты без токена и с невалидным токеном.

Frontend-тесты покрывают: состояния Loading/Empty/Error, i18n (наличие
только русских строк, дефолтная локаль), Module Registry (резолв
demo-модуля, безопасный `null` для незарегистрированных модулей).

## Production build

```bash
# Backend — просто запуск, ничего собирать не нужно
uvicorn app.server:app --host 0.0.0.0 --port $PORT

# Frontend
cd frontend && npm run build   # tsc -b && vite build → frontend/dist
```

## Деплой на Railway

Два отдельных Railway-сервиса на этот же репозиторий:
- **Backend**: root — корень репозитория, использует `Procfile` /
  `railway.json` (там же). Healthcheck — `/health`.
- **Frontend**: root — `frontend/`, свой `railway.json`, раздаёт
  собранный `dist/` через `serve`.

Пошаговый чек-лист переменных окружения и настройки — в
[`docs/MANUAL_STEPS.md`](docs/MANUAL_STEPS.md).

## Известные ограничения текущей версии (Core v1)

- `nexa_sessions` как отдельная таблица не создана — сессии стейтлес
  (короткоживущий подписанный JWT). Обоснование — в комментарии в
  `migrations/0001_nexa_core.sql`.
- `ModuleContext` (единый API для модулей, п.60 спецификации) пока не
  выделен отдельно — модули используют общие hooks Core напрямую. Не
  блокирует текущую архитектуру, можно добавить позже без breaking change.
- Полноценная админка (включение/выключение модулей через UI) не
  реализована — по спецификации (п.62) для Core v1 это не обязательно.
- E2E-тесты (Playwright) не добавлены — только unit/component-тесты
  (pytest, Vitest + React Testing Library).
