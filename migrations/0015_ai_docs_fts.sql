-- ============================================================
-- CodeNexa System — AI Docs migration 0015
-- Full-text search вместо `content_blocks::text ilike '%...%'`
-- (F-017 из production-аудита 22.08.2026: ILIKE по касту jsonb->text
-- не масштабируется — full table scan на каждый поиск, без индекса).
-- ============================================================

-- IMMUTABLE — обязательное требование для использования внутри
-- GENERATED ALWAYS AS (...) STORED ниже. Конкатенирует все "text"
-- поля из content_blocks (jsonb-массив [{"type":..,"text":..}, ...])
-- в одну строку для индексации.
create or replace function nexa_docs_extract_block_text(blocks jsonb)
returns text
language sql
immutable
parallel safe
as $$
  select coalesce(string_agg(elem->>'text', ' '), '')
  from jsonb_array_elements(coalesce(blocks, '[]'::jsonb)) as elem
$$;

-- STORED generated column — вычисляется автоматически при INSERT/UPDATE
-- (в т.ч. один раз для уже существующих строк при выполнении этой
-- миграции), не требует отдельного триггера на синхронизацию.
alter table nexa_docs_documents
  add column if not exists search_text tsvector
  generated always as (
    to_tsvector('russian', coalesce(title, '') || ' ' || nexa_docs_extract_block_text(content_blocks))
  ) stored;

create index if not exists idx_nexa_docs_documents_search_text
  on nexa_docs_documents using gin (search_text);
