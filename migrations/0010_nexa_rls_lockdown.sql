-- ============================================================
-- CodeNexa System — migration 0010
-- SEC-001 / P0-01 (production-аудит 22.08.2026): критическая находка,
-- подтверждена прямым запросом к живой БД перед этой миграцией:
--   - RLS был выключен на ВСЕХ nexa_* таблицах;
--   - anon и authenticated имели полный DELETE/INSERT/SELECT/UPDATE/
--     TRUNCATE на ВСЕХ nexa_* таблицах, включая nexa_users;
--   - приложение НЕ использует Supabase Data API/PostgREST/anon key
--     нигде в коде (grep по app/ и frontend/src/) — весь доступ идёт
--     через прямое подключение DATABASE_URL;
--   - роль postgres (которой подключается backend через DATABASE_URL/
--     pooler) и service_role имеют rolbypassrls=true — эта миграция
--     их не затрагивает и не может сломать работу приложения.
--
-- Итог: раз Data API не нужен, безопаснее полностью закрыть доступ
-- anon/authenticated, чем писать owner-based RLS-политики для 14
-- таблиц вслепую под функциональность, которая не используется.
--
-- ПРИМЕНЕНО НАПРЯМУЮ к продовой Supabase (hbzomngnrwzltztlnynh) через
-- Supabase MCP 23.08.2026 и ПРОВЕРЕНО там же (RLS enabled=true на всех
-- 14 таблицах, anon/authenticated grants пусты, postgres/service_role
-- не затронуты, чтение данных работает). Этот файл — для истории
-- миграций и для восстановления на новом окружении (staging/dev).
-- ============================================================

revoke all privileges on
  nexa_users,
  nexa_modules,
  nexa_user_modules,
  nexa_projects,
  nexa_notifications,
  nexa_settings,
  nexa_favorites,
  nexa_history,
  nexa_docs_templates,
  nexa_docs_documents,
  nexa_docs_versions,
  nexa_docs_shares,
  nexa_docs_conversations,
  nexa_docs_idempotency_keys
from anon, authenticated;

-- Защита от будущих таблиц в этой схеме, созданных без явного grant-ревью.
alter default privileges in schema public revoke all on tables from anon, authenticated;

-- Defense-in-depth: даже если grants когда-нибудь по ошибке вернут —
-- RLS без единой policy даёт honest default-deny для anon/authenticated,
-- при этом НЕ влияет на postgres/service_role (rolbypassrls=true).
alter table nexa_users enable row level security;
alter table nexa_modules enable row level security;
alter table nexa_user_modules enable row level security;
alter table nexa_projects enable row level security;
alter table nexa_notifications enable row level security;
alter table nexa_settings enable row level security;
alter table nexa_favorites enable row level security;
alter table nexa_history enable row level security;
alter table nexa_docs_templates enable row level security;
alter table nexa_docs_documents enable row level security;
alter table nexa_docs_versions enable row level security;
alter table nexa_docs_shares enable row level security;
alter table nexa_docs_conversations enable row level security;
alter table nexa_docs_idempotency_keys enable row level security;
