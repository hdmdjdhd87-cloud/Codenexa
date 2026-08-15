# MANUAL STEPS — что нужно сделать руками

Этот файл — единственное место, куда я (ассистент) добавляю шаги, которые
не могу выполнить сам из своей песочницы (нет сети до supabase.co,
api.telegram.org, railway.app). Отмечай выполненное `[x]`, обновляю файл
по мере продвижения по этапам.

---

## 1. База данных (Supabase SQL Editor)

Открой https://supabase.com/dashboard → проект `vlpgdiivliozzhacymaw` → **SQL Editor**.

- [ ] Выполнить `migrations/0001_nexa_core.sql` целиком (создаёт все таблицы `nexa_*`, старые таблицы не трогает — безопасно перезапускать, использует `IF NOT EXISTS`).
- [ ] Выполнить `migrations/0002_nexa_seed_demo_module.sql` (добавляет demo-модуль для проверки Module Registry).
- [ ] **НОВОЕ — Выполнить `migrations/0003_ai_docs.sql`** (таблицы AI Docs: nexa_docs_templates/documents/versions).
- [ ] **НОВОЕ — Выполнить `migrations/0004_ai_docs_seed_templates.sql`** (4 реальных шаблона: деловое письмо, заявление, расписка, договор оказания услуг).
- [ ] **НОВОЕ — Выполнить `migrations/0005_register_ai_docs_module.sql`** (регистрирует AI Docs в каталоге CodeNexa — без этого модуль не появится на Главной/в Каталоге).
- [ ] Проверить, что появились таблицы: `nexa_users`, `nexa_modules`, `nexa_user_modules`, `nexa_favorites`, `nexa_projects`, `nexa_history`, `nexa_notifications`, `nexa_settings`, `nexa_docs_templates`, `nexa_docs_documents`, `nexa_docs_versions`.
- [ ] Проверить, что старые таблицы (`services`, `bookings`, `working_hours`, `admin_users`, `audit_log`, `blocked_slots`, `booking_attempts`, `breaks`, `reviews`, `settings`) остались без изменений.

## 2. Railway — backend сервис

- [ ] Создать новый Railway-сервис на этот же репозиторий (`g848597/Codenexa2`), ветка `main`, root — корень репо (там `Procfile` и `railway.json`).
- [ ] Задать переменные окружения в Railway → Variables (см. разбор ниже — часть значений из старых проектов, часть нужно взять заново):

  **Подтверждено, использовать как есть:**
  - `ENVIRONMENT=production`
  - `TELEGRAM_BOT_TOKEN` — токен бота `CodeNexaminiappBot` (тот, что уже прислала — имя бота совпадает с проектом, это правильный токен).
  - `JWT_SECRET` — тот, что уже сгенерирован (длинная случайная строка), можно переиспользовать.

  **Нужно взять заново (НЕ из старого списка секретов):**
  - `DATABASE_URL` — строка подключения именно к проекту `vlpgdiivliozzhacymaw` (Supabase Dashboard → этот проект → Settings → Database → Connection string → Transaction pooler, порт 6543). ⚠️ В присланном списке `DATABASE_URL` указывал на СТАРЫЙ проект `temjwwglowbuarxuixpa` — его использовать нельзя, туда наши `nexa_*` миграции не попадут.
  - `SUPABASE_SERVICE_ROLE_KEY` — из Supabase Dashboard → `vlpgdiivliozzhacymaw` → Settings → API Keys (не из старого проекта).
  - `CORS_ORIGINS` — появится после деплоя frontend-сервиса (Этап 5).

  **Nice-to-have (не используется кодом сейчас, но пусть будет готово на будущее — для Supabase Storage/Auth):**
  - `SUPABASE_SERVICE_ROLE_KEY` — вставь `sb_secret_...` ключ **только в Railway → Variables** (не в файлы, не в git). Backend уже умеет читать эту переменную (`app/config.py`), но пока никакой код её не вызывает.
  - Publishable-ключ (`sb_publishable_...`) сохранять отдельно не нужно: фронтенд обращается только к нашему backend (`VITE_API_BASE_URL`), не к Supabase напрямую.

  **НЕ добавлять в этот сервис** (относятся к другим/старым проектам — sports-бот, AI Sport и т.п.): `TELEGRAM_WEBHOOK_SECRET`, `ADMIN_TELEGRAM_IDS`, `ADMIN_EMAILS`, `CACHE_TTL`, `REQUEST_DELAY_MS`, `FOOTBALLDATA_API_KEY`, `FOOTBALLDATA_BASE_URL`, `CLEARSPORTS_API_KEY`, `CLEARSPORTS_BASE_URL`.

- [ ] После первого деплоя проверить `https://<backend-домен>/health` → должен вернуть `{"status":"ok"}`.
- [ ] **НОВОЕ — ВАЖНО**: после деплоя коммита с OCR (`039b79d` и позже) проверить, что билд backend прошёл успешно и `nixpacks.toml` подтянул `tesseract-ocr`. Я не могу проверить это сам — если билд упадёт или OCR будет возвращать ошибку "tesseract is not installed" — пришли Build Logs из Railway, разберём.
- [ ] Проверить `https://<backend-домен>/ready` → `database: true` (подтверждает, что `DATABASE_URL` рабочий).

## 3. Telegram — настройка Mini App

- [ ] В @BotFather: `/mybots` → выбрать бота → **Bot Settings → Menu Button** (или `/setmenubutton`) → указать URL фронтенда (появится после Этапа 5, когда сделаю frontend + Railway-деплой для него).
- [ ] Либо через `/newapp`, если нужен отдельный Mini App (не просто menu button).
- [ ] Проверить открытие Mini App внутри самого Telegram (не в обычном браузере) — только там будет настоящий `window.Telegram.WebApp` с реальным `initData`.

## 4. Frontend — Railway сервис

Frontend готов (Этап 5 выполнен, build проходит, тесты 10/10 зелёные).

- [ ] Создать отдельный Railway-сервис на этот же репозиторий, но с **Root Directory = `frontend`** (в Railway это настраивается в Settings сервиса). Там уже лежит `frontend/railway.json` (build: `npm install && npm run build`, start: `npx serve -s dist -l $PORT`).
- [ ] Задать переменную `VITE_API_BASE_URL` = публичный URL backend-сервиса из шага 2 (например `https://codenexa-backend-production.up.railway.app`).
- [ ] После деплоя открыть URL фронтенда в обычном браузере — должно показать экран "Откройте это приложение через Telegram" (это ожидаемо, AuthGate специально блокирует работу вне Telegram в production).
- [ ] Вернуться к шагу 2 и обновить `CORS_ORIGINS` backend-сервиса на реальный URL фронтенда (сейчас там `http://localhost:5173`).

## 5. Секреты — финальная проверка

- [ ] Убедиться, что `.env` (не `.env.example`) нигде не закоммичен — проверить `git log -p -- .env` пустой.
- [ ] Убедиться, что `TELEGRAM_BOT_TOKEN`, `JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` не встречаются в frontend-коде (`grep -r` по `frontend/src`).

---

*Обновляется по ходу работы. Последнее обновление: после Этапа 4 (backend + Telegram auth готовы и протестированы).*
