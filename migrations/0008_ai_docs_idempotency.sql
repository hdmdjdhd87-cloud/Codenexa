-- ============================================================
-- CodeNexa System — AI Docs migration 0008
-- Идемпотентность мутирующих запросов (п.7 промпта): защита от
-- двойного клика/повторной отправки на уровне БД, а не только
-- disabled-состоянием кнопки на фронтенде.
-- ============================================================

create table if not exists nexa_docs_idempotency_keys (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references nexa_users(id) on delete cascade,
  scope           text not null,           -- 'create_document' | 'restore_version' | 'create_share' | 'duplicate_document'
  idempotency_key text not null,
  response_body   jsonb,                   -- null пока запрос ещё выполняется (см. app/repositories/idempotency.py)
  created_at      timestamptz not null default now(),
  unique (user_id, scope, idempotency_key)
);
create index if not exists idx_nexa_docs_idem_created_at on nexa_docs_idempotency_keys (created_at);
