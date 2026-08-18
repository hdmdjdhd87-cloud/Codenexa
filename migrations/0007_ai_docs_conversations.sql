-- ============================================================
-- CodeNexa System — AI Docs migration 0007
-- Состояние диалога с Document Intelligence Engine (rule-based,
-- без внешнего AI). Одна таблица вместо conversations+messages —
-- история сообщений хранится внутри как jsonb-массив (осознанное
-- упрощение, не overengineering: объём одного диалога небольшой,
-- отдельная таблица messages не даёт практической пользы сейчас).
-- ============================================================

create table if not exists nexa_docs_conversations (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references nexa_users(id) on delete cascade,
  document_id    uuid references nexa_docs_documents(id) on delete set null,
  status         text not null default 'idle'
                 check (status in ('idle','collecting','ready_to_create','done')),
  intent         text,
  template_key   text,
  field_values   jsonb not null default '{}'::jsonb,
  awaiting_field text,
  messages       jsonb not null default '[]'::jsonb,  -- [{role:'user'|'agent', text, created_at}, ...]
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index if not exists idx_nexa_docs_conversations_user_id on nexa_docs_conversations (user_id);
create index if not exists idx_nexa_docs_conversations_status on nexa_docs_conversations (status);

do $$
begin
  execute 'drop trigger if exists trg_nexa_docs_conversations_updated_at on nexa_docs_conversations;
    create trigger trg_nexa_docs_conversations_updated_at
    before update on nexa_docs_conversations
    for each row execute function nexa_set_updated_at();';
end $$;
