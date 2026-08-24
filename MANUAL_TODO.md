# MANUAL_TODO.md — что осталось сделать вручную

Обновлено после production-аудита (PDF, 22.08.2026), предоставленного
пользователем. Разделено на две части: (А) исходный список из первой
сессии, (Б) статус по пунктам аудита.

---

# Б. Статус по production-аудиту (22.08.2026)

Аудит подтвердил и потребовал исправить широкий список P0–P4 пунктов.
Я честно прошёлся по каждому — не помечаю ничего "готово", если не
проверил сам. Особо рискованные пункты (в первую очередь RLS на живой
проде) **намеренно не применены автоматически** — ошибка там может
либо сломать всё приложение, либо оставить дыру, а я не могу
протестировать это против вашей реальной Supabase.

## Сделано и запушено

- **SEC-002 (config drift)** — commit `a169b9b`. `app/database.py`:
  `extract_supabase_project_ref()` + опциональный fail-fast
  `EXPECTED_DB_PROJECT_REF`; `.env.example` больше не содержит
  захардкоженный (возможно, устаревший) Supabase URL. 9 тестов.
- **SEC-003 / F-003 / F-004 (idempotency race)** — commit `a169b9b`.
  `app/repositories/idempotency.py` переписан на recoverable state
  machine (pending/completed/failed + lease + request_hash), не держит
  DB-connection во время `work_fn()`. Миграция
  `migrations/0009_ai_docs_idempotency_state_machine.sql` — применена
  к реальной БД и проверена (см. ниже). 12 тестов на то, что тестируется
  без живого Postgres; гоночные сценарии (два конкурентных claim,
  recovery после краша) честно помечены как **NOT VERIFIED** — нужен
  integration-тест против реального Postgres.
- **SEC-001 / P0-01 (RLS/GRANT) — ИСПРАВЛЕНО, 23.08.2026.** Подключён
  Supabase MCP-коннектор, находка аудита проверена напрямую по факту
  (не по описанию из PDF) и подтверждена:
  - RLS был выключен на всех 14 таблицах `nexa_*`;
  - `anon` и `authenticated` имели полный `DELETE/INSERT/SELECT/UPDATE/
    TRUNCATE` на всех `nexa_*`, включая `nexa_users` — то есть у
    любого, кто знает публичный `anon key` проекта, был прямой доступ
    ко всем данным всех пользователей в обход бэкенда через Supabase
    REST API;
  - проверено (`grep`), что приложение нигде не использует Supabase
    Data API/PostgREST/`anon key` — весь доступ идёт через
    `DATABASE_URL` (asyncpg), поэтому чинить это через RLS-политики
    было избыточно и рискованно — правильный фикс - `REVOKE`;
  - проверено, что роль `postgres` (которой подключается backend) и
    `service_role` имеют `rolbypassrls=true` — значит, включение RLS
    без единой policy (defense-in-depth) даёт честный default-deny для
    `anon`/`authenticated`, не затрагивая работу приложения.
  - Применена миграция `migrations/0010_nexa_rls_lockdown.sql` — REVOKE
    ALL от `anon`/`authenticated` на всех 14 таблицах + `ALTER DEFAULT
    PRIVILEGES` (защита от будущих таблиц) + `ENABLE ROW LEVEL SECURITY`
    на всех 14 таблицах.
  - **Проверено после применения:** `anon`/`authenticated` — 0 grants на
    все `nexa_*`; `postgres` — все права сохранены, не тронуты; чтение
    данных (`select count(*) from nexa_docs_documents`) работает
    нормально; RLS `enabled=true` на всех 14 таблицах.

**⚠️ Требуется от вас:** ничего — миграции `0009` и `0010` уже применены
напрямую к продовой БД через MCP и проверены. Файлы синхронизированы в
`migrations/` для истории/восстановления на новом окружении.

## Остаётся — крупные отдельные задачи, не тронуто в этой сессии

### F-011 — Railway healthcheck / F-014 — CORS / F-015 — ai_is_configured — ИСПРАВЛЕНО
Все три — код-ревью, без риска для прода, все проверены тестами:
- **F-011**: `railway.json` указывал `healthcheckPath: /health` (liveness-
  only, не проверяет БД) — при деплое Railway мог переключить трафик на
  инстанс с нерабочим подключением к БД. Исправлено на `/ready` (код
  `/health` vs `/ready` уже был правильно разделён в `app/routers/health.py`,
  проблема была только в конфиге).
- **F-014**: CORS `allow_methods`/`allow_headers` были `["*"]`. Сужено до
  реально используемого набора (проверено grep по всему `frontend/src`):
  методы `GET/POST/PATCH/DELETE`, заголовки `Authorization/Content-Type/
  Idempotency-Key`. 3 теста на preflight-запрос.
- **F-015**: `ai_is_configured()` могла вернуть `True` по наличию
  `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` в окружении, даже когда
  `get_ai_provider()` всё равно всегда возвращает `UnavailableAIProvider`
  — рассинхрон, который вводил бы фронтенд в заблуждение ("AI доступен",
  хотя каждый вызов падает). Теперь `ai_is_configured()` структурно
  следует за `get_ai_provider()` — рассинхрон невозможен. 4 теста.

### P0-09 — Rate limiting — ИСПРАВЛЕНО, 23.08.2026
Реализовано на Postgres, без Redis (осознанное решение — аудит сам
предупреждает не тащить Redis "про запас"; текущий масштаб этого не
требует, а сама схема легко заменяется на Redis при реальном росте):
- `app/middleware/rate_limit_tiers.py` — чистая функция сопоставления
  пути/метода с тиром лимита (auth/mutation/read/ocr/export/
  public_share/general), 18 тестов, включая регрессионные на порядок
  правил (export не должен перехватывать все `/documents/{id}/...`).
- `app/middleware/rate_limit.py` — ASGI middleware: определение
  identity (`user:<id>` после auth или `ip:<addr>` до auth/для
  публичных ссылок, с учётом `X-Forwarded-For` — Railway проксирует
  трафик), атомарный fixed-window upsert-инкремент в Postgres,
  fail-open при недоступности БД (rate limiting — defense-in-depth,
  не единственная линия защиты). 11 тестов.
- Подключено в `app/server.py` — важно: middleware добавлен ДО
  `CORSMiddleware`, чтобы CORS оставался снаружи и 429-ответы получали
  корректные CORS-заголовки.
- Миграции `0011` (таблица) и `0012` (RLS для консистентности) —
  применены к продовой БД через Supabase MCP и проверены напрямую:
  атомарный upsert отработал корректно (1→2 в одном window_start),
  `anon`/`authenticated` не получили grants (сработала `ALTER DEFAULT
  PRIVILEGES` из миграции 0010), RLS включён, `postgres`-запись/
  удаление не затронуты.

**Честно, NOT VERIFIED:** реальное поведение под нагрузкой (много
одновременных запросов от одного identity, поведение при реальном 429)
не тестировалось интеграционно — в песочнице нет живого Postgres для
`TestClient`. Значения лимитов (20-180 запросов/60 сек по тирам) —
консервативно-щедрые стартовые оценки, не откалиброваны по реальным
метрикам (которых пока нет — аудит сам это отмечает).

### P0-10 / SEC-004 — Admin RBAC — ИСПРАВЛЕНО, 23.08.2026
Схема `admin_roles/admin_permissions/admin_role_permissions/admin_users/
admin_audit_log` (`migrations/0013_admin_rbac.sql`), не хардкодит admin
по Telegram ID — owner назначается через seed-запись в `admin_users` по
`telegram_user_id`, дальше всё решает БД-схема ролей/прав.

- 5 ролей: owner/security_admin/operator/support/content_admin с разными
  наборами прав (owner получает все права на уровне кода, не отдельными
  строками — не может "забыть" выдать себе новое право, когда оно
  появляется в системе).
- `admin_audit_log` — append-only (`REVOKE DELETE, UPDATE`), пишется
  ПОСЛЕ успешного действия (неудавшиеся попытки не аудируются отдельной
  строкой), IP хранится только как sha256-хэш (не сырой адрес).
- `app/auth/middleware.get_current_user_id` теперь дополнительно
  проверяет `is_blocked`/`sessions_valid_from` из `nexa_users`
  (`migrations/0014_nexa_users_moderation.sql`) — без этого "заблокировать
  пользователя"/"отозвать сессии" из будущей админки были бы
  косметическими действиями без реального эффекта на уже выданный JWT.
  Это добавляет 1 DB-запрос на КАЖДЫЙ авторизованный запрос во всём
  приложении — сознательный trade-off, fail-CLOSED (503) при недоступности
  БД, а не fail-open (это security-проверка, не rate-limiting).
- Backend API: `GET /api/v1/admin/me,/dashboard,/users,/users/{id},
  /audit-log`, `POST /users/{id}/block,/unblock,/revoke-sessions`.
- **Применено к реальной БД и проверено напрямую**: owner-запись создана
  (`telegram_user_id=8129422076`, роль `owner`, status `active`), RLS
  `enabled=true` на всех 5 admin-таблицах, `anon`/`authenticated` — 0
  grants, новые колонки на `nexa_users` читаются корректно.
- 21 новый тест (middleware blocked/revoked/db-down, RBAC permission
  resolution, admin router через TestClient) — все проходят.

**Осталось (не блокирует прод, но не готово):**
- Эндпоинты под `documents.moderate`, `system.manage`, `admins.manage` —
  ещё не реализованы. `security.view` (rate-limit hits) и `shares.revoke`
  реализованы (см. `06d14f1`).
- Гоночные сценарии RBAC (два одновременных запроса на смену роли и
  т.п.) — **NOT VERIFIED**, нет живого Postgres для интеграционных
  тестов в песочнице.

### P0-06 — Обновление зависимостей (python-jose, Pillow) — ИСПРАВЛЕНО, 23.08.2026
- `python-jose[cryptography]`: 3.3.0 → 3.5.0 (патч-версии внутри той же
  мажорной линии).
- `Pillow`: 10.4.0 → 12.3.0 (два мажорных скачка, но в кодовой базе
  используется ровно в одном месте — `app/document_engine/ocr.py` —
  через `Image.open()` + `.load()`, самое стабильное API, не менявшееся
  между этими версиями).
- Проверено НЕ только прогоном тестов: ручной sanity-запуск полного OCR-
  пайплайна на английском тексте через реальный Tesseract + Pillow 12.3.0
  (текст распознан), ручной JWT create/verify roundtrip с python-jose 3.5.0
  (токен создан, подписан, проверен). `app.server:app` по-прежнему
  импортируется. Полный тест-сьют: 216 passed / 1 failed (тот же
  предсуществующий OCR-кириллица флейк, не связан с апгрейдом).

### P1 — Reliability по остальным пунктам
**F-012/F-013 — ИСПРАВЛЕНО, 23.08.2026** (см. `7430c9d`): safe retry
policy для `apiRequest` (GET/HEAD всегда, мутации — только с
Idempotency-Key; exponential backoff+jitter; не ретраит семантические
4xx) + таймаут(30s)/401-восстановление для `downloadAuthorizedFile`
(раньше не было ни того, ни другого — мог зависнуть навсегда). 18
новых тестов.

**Осталось из P1:** circuit breaker/backpressure для AI/OCR, `/health`
vs `/ready` разделение (F-011 уже поправлен параллельной сессией — см.
`50c9380` — но стоит перепроверить `railway.json` живьём в Railway
dashboard, я не могу подтвердить, что там реально настроено), не
держать DB-connection во время CPU-heavy work (частично уже сделано
в idempotency.py, `a169b9b`), background jobs для тяжёлых OCR/export.

### P2 — Scale — ЧАСТИЧНО ИСПРАВЛЕНО, 23.08.2026
- **F-017 (FTS вместо ILIKE)** — `b7d47e2`. `search_text` STORED
  tsvector-колонка + GIN-индекс, безопасная токенизация запроса в
  Python (`_build_prefix_tsquery`), проверено вживую на реальной БД.
- **Retention/cleanup** — `855e176` + `b134762`. pg_cron установлен,
  3 ежедневных job'а: idempotency-ключи (7 дней), expired/revoked
  shares (30 дней после истечения), rate-limit окна (3 дня). Все
  проверены вживую (job'ы active=true, функции вызваны вручную без
  ошибок).
- **Pagination** — `935e8aa`. `GET /documents` и `GET /notifications`
  теперь с `page`/`page_size` (лимит 200), defense-in-depth (капается
  и в роутере, и в repo-функции). Обратно совместимо — фронтенд пока
  не передаёт эти параметры, но граница на будущее есть.

**Осталось из P2:** connection budget (общий лимит соединений к БД на
весь деплой при N инстансов Railway), compound indexes по факту
реальных query plans (аудит сам говорит не делать это превентивно —
"в реальной БД сейчас очень маленький объём данных... масштаб не
доказан"), frontend UI для "следующей страницы" (infinite scroll/кнопка
"Ещё") — backend готов, фронтенд пока нет.

### P3 — Frontend — ЧАСТИЧНО ИСПРАВЛЕНО, 23.08.2026
**Разбит `AiDocsApp.tsx`** (`cf11365`) — было 1382 строки в одном
файле, стало 8 файлов (117-строчный оркестратор + 7 view-модулей).
Проверено: `tsc -b` чисто, размер бандла идентичен до/после (нет
дублирования кода), 32/32 frontend-тестов проходят.

**Осталось из P3:** `views/DocumentPreviewView.tsx` всё ещё крупный
(612 строк — версии/сравнение/анализ/шаринг/дублирование в одном
файле), можно дробить дальше на VersionHistory/CompareView/
AnalysisPanel/ShareDialog отдельным заходом. E2E Playwright — не
реализовано вообще. Visual regression — не реализовано (и не может
быть реализовано мной без реального Telegram-клиента).

### P4 — Admin panel — ЧАСТИЧНО ИСПРАВЛЕНО, 23.08.2026
Backend RBAC (см. выше) + первая версия UI (`frontend/src/features/admin/AdminPage.tsx`):
вкладки Обзор/Пользователи/Журнал, блокировка/разблокировка/отзыв
сессий с инлайн-подтверждением, доступ виден только реальным админам
(тихий redirect для остальных — не граница безопасности, только UX,
реальная защита на backend). Пункт меню в Профиле, виден только
админам. 4 новых frontend-теста.

**Осталось из P4:** остальные разделы админки из спеки аудита (Modules,
Templates, Documents, Shares, AI/Quotas, Jobs, Security, System) —
только Users/Dashboard/Audit Log реализованы, там backend уже покрывает
конкретно users.view/block/revoke_sessions и audit.view. Impersonation,
feature flags, maintenance mode — не реализовано вообще.

## Что НЕ делать по прямому указанию аудита (и я это соблюдаю)
- Не переписывать backend с нуля.
- Не хардкодить admin по одному Telegram ID.
- Не добавлять бесконечные retry.
- Не редактировать уже применённую миграцию `0008` задним числом (я
  добавил отдельную `0009`).
- Не объявлять проект production-ready только потому, что backend-тесты
  зелёные — не объявляю.

---

# А. Список из первой сессии (см. историю коммитов до `aa08658`)

## 1. Миграции к реальной БД

Все миграции `0001`–`0010` применены к продовой Supabase и проверены
напрямую (см. раздел Б выше). Ничего применять вручную не нужно.

## 2. Visual QA на реальных экранах

Я не могу открыть Telegram и не могу увидеть реальный рендер на
устройстве. Нужно пройти вживую на 360/375/390/412px — см. список
конкретных экранов для проверки в истории предыдущей версии этого
файла (git log MANUAL_TODO.md) или просто пройтись по всем новым
экранам AI Docs.

## 3. Тестовое покрытие

Backend: ≈159 тестов (было 144, +15 после аудита). Frontend: 10 тестов
(без изменений — новые React-компоненты пока не покрыты).

**Известный нестабильный тест:** `test_ocr.py::test_extract_text_from_image_cyrillic`
падает в песочнице (нет `rus.traineddata`) — проверьте в production,
что кириллический пакет Tesseract там установлен. Backend сейчас:
216 тестов (было 159), +21 из admin RBAC.

---

Хронология коммитов:
1. `a602fa3` — Restore + Compare версий (backend)
2. `793a175` — Restore + Compare + Анализировать (frontend)
3. `200ddf6` — редактирование документа через чат
4. `205a5f3` — OCR → автозаполнение полей
5. `090ebaa` — восстановление незавершённого диалога
6. `6b2218a` — идемпотентность create/restore/duplicate/share (v1)
7. `aa08658` — MANUAL_TODO.md (первая версия)
8. `a169b9b` — SEC-002 config drift + SEC-003/F-003/F-004 idempotency state machine (v2)
9. `1a6072f` — SEC-001/P0-01 RLS/GRANT lockdown (другая параллельная сессия)
10. `50c9380` — F-011 healthcheck / F-014 CORS / F-015 ai_is_configured (параллельная сессия)
11. `7f66313` — P0-09 rate limiting на Postgres (параллельная сессия)
12. `ea56d90` — P0-10/SEC-004 Admin RBAC
13. `fe8a619` — P0-06 апгрейд python-jose/Pillow
14. `13cae58` — переименование мигр. 0011/0012 (коллизия с параллельной сессией) + обновление MANUAL_TODO.md
15. `212a095` — P4 Admin panel UI
16. `7430c9d` — F-012/F-013 retry policy + download timeout/401-recovery
17. `06d14f1` — security.view (rate-limit hits) + shares.revoke эндпоинты
18. `b7d47e2` — F-017 FTS вместо ILIKE (search_text tsvector + GIN)
19. `855e176` — retention/cleanup для idempotency-ключей (pg_cron)
20. `b134762` — retention/cleanup для expired shares и rate-limit окон
21. `935e8aa` — пагинация GET /documents и GET /notifications
22. `cf11365` — разбит AiDocsApp.tsx на 8 feature-модулей

