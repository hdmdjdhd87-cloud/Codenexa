-- ============================================================
-- CodeNexa System — AI Docs migration 0016
-- Retention/cleanup для nexa_docs_idempotency_keys (аудит 22.08.2026,
-- раздел 10 'Database deep review': 'idempotency_keys нужен
-- retention/cleanup').
--
-- Без cleanup таблица растёт бесконечно — каждый create/restore/
-- duplicate/share пишет новую строку и никогда её не удаляет.
-- Ключи нужны только на время, пока клиент может повторить один и тот
-- же запрос (несколько секунд-минут после отправки) — 7 дней с большим
-- запасом покрывает любой реалистичный сценарий "открыл вкладку через
-- день и нажал ещё раз ту же кнопку", но не даёт таблице расти вечно.
-- ============================================================

create extension if not exists pg_cron;

create or replace function nexa_docs_cleanup_idempotency_keys()
returns void
language sql
as $$
  delete from nexa_docs_idempotency_keys
  where created_at < now() - interval '7 days';
$$;

-- Ежедневно в 03:17 UTC (намеренно не ровно в полночь/на круглый час —
-- избегаем толчеи с другими job'ами, которые типично планируют на
-- 00:00/01:00 и т.п.). Явный IF NOT EXISTS через DO-блок — в отличие
-- от `SELECT f() WHERE ...` без FROM, здесь однозначно гарантировано,
-- что cron.schedule() вызывается только когда job действительно
-- отсутствует (порядок вычисления target list vs WHERE в безусловном
-- SELECT неочевиден и не стоит на него полагаться для side-effecting
-- вызова).
do $$
begin
  if not exists (select 1 from cron.job where jobname = 'nexa-docs-cleanup-idempotency-keys') then
    perform cron.schedule(
      'nexa-docs-cleanup-idempotency-keys',
      '17 3 * * *',
      $sql$select nexa_docs_cleanup_idempotency_keys()$sql$
    );
  end if;
end;
$$;
