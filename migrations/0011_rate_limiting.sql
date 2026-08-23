-- ============================================================
-- CodeNexa System — migration 0011
-- P0-09 (production-аудит 22.08.2026): rate limiting без Redis.
-- Осознанное решение: на текущем масштабе (1 инстанс backend, малый
-- траффик) отдельный Redis добавлять преждевременно — аудит сам
-- предупреждает не тащить инфраструктуру "про запас". Fixed-window
-- счётчик в Postgres с атомарным upsert решает задачу без нового
-- сервиса; если понадобится Redis при реальном росте — эта таблица
-- легко заменяется на distributed store без изменения контракта
-- (app/middleware/rate_limit.py).
--
-- ПРИМЕНЕНО НАПРЯМУЮ к продовой Supabase (hbzomngnrwzltztlnynh) через
-- Supabase MCP 23.08.2026 и ПРОВЕРЕНО там же (атомарный upsert-инкремент
-- отработал корректно на двух последовательных вызовах: 1 -> 2 в одном
-- window_start; anon/authenticated не получили grants благодаря ALTER
-- DEFAULT PRIVILEGES из миграции 0010; RLS включён отдельной миграцией
-- 0012 для консистентности с остальными таблицами).
-- ============================================================

create table if not exists nexa_rate_limit_hits (
  identity      text not null,        -- 'user:<uuid>' (после auth) или 'ip:<addr>' (до auth/публичные ссылки)
  scope         text not null,        -- 'auth' | 'mutation' | 'read' | 'ocr' | 'export' | 'public_share' | 'general'
  window_start  timestamptz not null, -- начало fixed-window (округлено вниз до window_seconds)
  request_count integer not null default 1,
  primary key (identity, scope, window_start)
);

-- Для periodic cleanup старых окон (запускается вручную/по cron —
-- см. MANUAL_TODO.md, автоматического планировщика в проекте нет).
create index if not exists idx_nexa_rate_limit_window_start on nexa_rate_limit_hits (window_start);
