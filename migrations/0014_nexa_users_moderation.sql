-- ============================================================
-- CodeNexa System — Core migration 0014
-- Поля модерации пользователя на nexa_users, нужны для admin
-- actions users.block / users.revoke_sessions (P0-10 из аудита
-- 22.08.2026). Отдельная миграция от 0013 (RBAC-схема) — разные
-- по сути изменения (0013 создаёт новые таблицы, эта меняет
-- существующую nexa_users).
-- ============================================================

alter table nexa_users
  add column if not exists is_blocked boolean not null default false,
  add column if not exists blocked_at timestamptz,
  add column if not exists blocked_reason text,
  -- Токены с iat (issued-at) раньше этой отметки считаются
  -- отозванными — "отозвать все сессии" = проставить now(). Не
  -- ломает пользователя навсегда: следующий Telegram-логин выдаёт
  -- новый токен с iat > sessions_valid_from автоматически.
  add column if not exists sessions_valid_from timestamptz not null default now();
