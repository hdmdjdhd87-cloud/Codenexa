-- ============================================================
-- CodeNexa System — Seed 0002
-- Единственный "fake"-объект во всей системе: демонстрационный
-- модуль для проверки Module Registry (registration → routing →
-- catalog display → open → favorite → history).
--
-- Это НЕ считается нарушением "NO FAKE DATA POLICY" (п.54),
-- т.к. явно разрешено п.14 и п.55 спецификации именно для проверки
-- архитектуры реестра модулей.
--
-- Удалить одной операцией после проверки:
--   delete from nexa_modules where module_key = 'codenexa-demo';
-- (связанные nexa_user_modules / nexa_favorites / nexa_history
--  удалятся каскадно благодаря on delete cascade / set null)
-- ============================================================

insert into nexa_modules (module_key, name, slug, description, category, icon, route, version, status, is_featured, sort_order)
values (
  'codenexa-demo',
  'CodeNexa Demo',
  'codenexa-demo',
  'Тестовый модуль для проверки архитектуры Module Registry.',
  'productivity',
  'demo',
  '/apps/codenexa-demo',
  '1.0.0',
  'active',
  false,
  999
)
on conflict (module_key) do nothing;
