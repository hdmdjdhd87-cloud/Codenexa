-- ============================================================
-- CodeNexa System — AI Docs migration 0003
-- Отдельный модуль экосистемы. Новые таблицы с префиксом nexa_docs_,
-- не пересекаются с существующими nexa_* и тем более со старым
-- проектом (services/bookings/...). Ничего не удаляет и не меняет.
-- ============================================================

-- ------------------------------------------------------------
-- nexa_docs_templates — шаблоны документов (registry-driven,
-- как и nexa_modules: новый шаблон = INSERT, без изменения кода)
-- ------------------------------------------------------------
create table if not exists nexa_docs_templates (
  id            uuid primary key default gen_random_uuid(),
  template_key  text not null unique,
  name          text not null,
  category      text not null,        -- 'business' | 'personal' | 'legal' | 'universal'
  description   text,
  -- Схема полей для формы заполнения: [{key, label, type, required}, ...]
  fields_schema jsonb not null default '[]'::jsonb,
  -- Тело документа с плейсхолдерами {{field_key}}, разбитое на блоки:
  -- [{type:'heading'|'paragraph'|'signature_line', text:'...'}]
  body_template jsonb not null default '[]'::jsonb,
  is_active     boolean not null default true,
  sort_order    integer not null default 0,
  created_at    timestamptz not null default now()
);
create index if not exists idx_nexa_docs_templates_category on nexa_docs_templates (category);

-- ------------------------------------------------------------
-- nexa_docs_documents — документы пользователя
-- ------------------------------------------------------------
create table if not exists nexa_docs_documents (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references nexa_users(id) on delete cascade,
  template_id   uuid references nexa_docs_templates(id) on delete set null,
  title         text not null,
  doc_type      text not null,     -- копия template.category на момент создания (для истории/поиска)
  -- Финальные значения полей формы (после заполнения пользователем)
  field_values  jsonb not null default '{}'::jsonb,
  -- Сгенерированные блоки содержимого (тот же формат, что body_template,
  -- но с уже подставленными значениями) — единственный источник
  -- правды для рендера DOCX/PDF и предпросмотра.
  content_blocks jsonb not null default '[]'::jsonb,
  is_favorite   boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists idx_nexa_docs_documents_user_id on nexa_docs_documents (user_id);
create index if not exists idx_nexa_docs_documents_created_at on nexa_docs_documents (created_at desc);

-- ------------------------------------------------------------
-- nexa_docs_versions — история версий документа
-- ------------------------------------------------------------
create table if not exists nexa_docs_versions (
  id             uuid primary key default gen_random_uuid(),
  document_id    uuid not null references nexa_docs_documents(id) on delete cascade,
  version_number integer not null,
  content_blocks jsonb not null,
  note           text,           -- 'Создан документ' / 'Изменён раздел ...' и т.п.
  created_at     timestamptz not null default now(),
  unique (document_id, version_number)
);
create index if not exists idx_nexa_docs_versions_document_id on nexa_docs_versions (document_id);

do $$
begin
  execute 'drop trigger if exists trg_nexa_docs_documents_updated_at on nexa_docs_documents;
    create trigger trg_nexa_docs_documents_updated_at
    before update on nexa_docs_documents
    for each row execute function nexa_set_updated_at();';
end $$;
