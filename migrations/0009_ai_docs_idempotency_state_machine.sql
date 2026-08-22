-- ============================================================
-- CodeNexa System — AI Docs migration 0009
-- Исправление SEC-003/F-003 из production-аудита (22.08.2026):
-- предыдущая реализация idempotency (0008) держала ключ "заклеймённым"
-- навсегда, если work_fn() падал с исключением — INSERT коммитился
-- отдельным auto-commit statement'ом без явной транзакции, и rollback
-- при исключении не происходил, вопреки комментарию в коде.
--
-- Правило проекта: не редактируем уже применённую 0008 задним числом,
-- добавляем недостающее новой миграцией (ALTER TABLE идемпотентен —
-- IF NOT EXISTS, безопасно перезапускать).
-- ============================================================

alter table nexa_docs_idempotency_keys
  add column if not exists state text not null default 'pending',
  add column if not exists lease_expires_at timestamptz not null default (now() + interval '2 minutes'),
  add column if not exists request_hash text,
  add column if not exists error_message text;

alter table nexa_docs_idempotency_keys
  drop constraint if exists nexa_docs_idempotency_keys_state_check;
alter table nexa_docs_idempotency_keys
  add constraint nexa_docs_idempotency_keys_state_check
  check (state in ('pending', 'completed', 'failed'));

-- Существующие строки (если 0008 уже была применена и что-то успело
-- записаться) — считаем завершёнными, если у них уже есть response_body,
-- иначе честно помечаем failed (лучше дать перезапросить, чем оставить
-- вечный pending без лиза).
update nexa_docs_idempotency_keys
set state = case when response_body is not null then 'completed' else 'failed' end
where state = 'pending' and created_at < now() - interval '1 minute';

create index if not exists idx_nexa_docs_idem_lease
  on nexa_docs_idempotency_keys (lease_expires_at)
  where state = 'pending';
