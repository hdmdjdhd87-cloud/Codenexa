-- ============================================================
-- CodeNexa System — migration 0012
-- Defense-in-depth для nexa_rate_limit_hits (миграция 0011): включение
-- RLS для консистентности с остальными nexa_* таблицами (см. 0010).
-- anon/authenticated и так не имели grants на эту таблицу (сработала
-- ALTER DEFAULT PRIVILEGES из 0010), но explicit RLS — дополнительный
-- слой на случай будущих ошибок в grants. postgres/service_role имеют
-- rolbypassrls=true — приложение не затронуто.
--
-- ПРИМЕНЕНО НАПРЯМУЮ к продовой Supabase (hbzomngnrwzltztlnynh) через
-- Supabase MCP 23.08.2026 и ПРОВЕРЕНО (relrowsecurity=true, запись/
-- удаление от имени postgres по-прежнему работает).
-- ============================================================

alter table nexa_rate_limit_hits enable row level security;
