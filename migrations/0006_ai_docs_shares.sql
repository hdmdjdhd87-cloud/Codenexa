-- ============================================================
-- CodeNexa System — AI Docs migration 0006
-- Безопасные view-only ссылки на документы (п.33 промпта).
-- ============================================================

create table if not exists nexa_docs_shares (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references nexa_docs_documents(id) on delete cascade,
  user_id      uuid not null references nexa_users(id) on delete cascade,
  token        text not null unique,   -- случайная строка, часть публичной ссылки
  expires_at   timestamptz,            -- null = бессрочно, пока не отозвана
  revoked_at   timestamptz,
  created_at   timestamptz not null default now()
);
create index if not exists idx_nexa_docs_shares_document_id on nexa_docs_shares (document_id);
create index if not exists idx_nexa_docs_shares_token on nexa_docs_shares (token);
