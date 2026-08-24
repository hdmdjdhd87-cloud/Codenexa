-- ============================================================
-- CodeNexa System — Core migration 0017
-- Retention/cleanup для nexa_docs_shares (истёкшие/отозванные) и
-- nexa_rate_limit_hits (старые окна) — продолжение 0016, тот же
-- пункт аудита 22.08.2026: "Удалять expired shares... и старые
-- rate-limit окна по lifecycle policy".
--
-- Отдельные функции (не одна общая) — если одна упадёт, это не
-- должно блокировать очистку остального; отдельные cron.job записи
-- по той же причине изолируют сбои друг от друга.
-- ============================================================

-- Shares: НЕ удаляем сразу по истечении expires_at/revoked_at —
-- 30-дневный запас после истечения/отзыва оставляет время на
-- расследование инцидента ("кто-то утверждает, что видел наш документ
-- по старой ссылке — когда именно она была активна и когда истекла?"),
-- не превращая таблицу в бесконечный архив.
create or replace function nexa_docs_cleanup_expired_shares()
returns void
language sql
as $$
  delete from nexa_docs_shares
  where (expires_at is not null and expires_at < now() - interval '30 days')
     or (revoked_at is not null and revoked_at < now() - interval '30 days');
$$;

-- Rate-limit окна — чисто операционные данные (не аудит), нужны только
-- для расчёта текущих лимитов и краткосрочной диагностики "почему меня
-- лимитнуло только что" — 3 дней с запасом достаточно.
create or replace function nexa_rate_limit_cleanup_old_windows()
returns void
language sql
as $$
  delete from nexa_rate_limit_hits
  where window_start < now() - interval '3 days';
$$;

do $$
begin
  if not exists (select 1 from cron.job where jobname = 'nexa-docs-cleanup-expired-shares') then
    perform cron.schedule(
      'nexa-docs-cleanup-expired-shares',
      '32 3 * * *',
      $sql$select nexa_docs_cleanup_expired_shares()$sql$
    );
  end if;

  if not exists (select 1 from cron.job where jobname = 'nexa-rate-limit-cleanup-old-windows') then
    perform cron.schedule(
      'nexa-rate-limit-cleanup-old-windows',
      '47 3 * * *',
      $sql$select nexa_rate_limit_cleanup_old_windows()$sql$
    );
  end if;
end;
$$;
