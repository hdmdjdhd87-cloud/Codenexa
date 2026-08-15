-- ============================================================
-- CodeNexa System — 0005: регистрация модуля AI Docs
-- Обычная запись в nexa_modules — Module Registry подхватывает её
-- автоматически, без изменения Home/Catalog/остального Core (п.13).
-- ============================================================

insert into nexa_modules (module_key, name, slug, description, category, icon, route, version, status, is_featured, sort_order)
values (
  'ai-docs',
  'AI Docs',
  'ai-docs',
  'Создавайте, заполняйте и экспортируйте документы по шаблону в DOCX и PDF.',
  'docs',
  null,
  '/apps/ai-docs',
  '0.1.0',
  'active',
  true,
  1
)
on conflict (module_key) do update set
  description = excluded.description,
  is_featured = excluded.is_featured,
  sort_order = excluded.sort_order;
