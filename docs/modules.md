# Как добавить новый модуль в CodeNexa System

Этот документ — главный ориентир для добавления любого будущего продукта
(NexaFiles, NexaPost, NexaDocs и т.д.) в экосистему без переписывания Core.

Модульная архитектура построена так, что Core **никогда** не содержит
`if (module_key === "nexa-files")`. Всё регистрозависимое — на двух уровнях:

1. **База данных** (`nexa_modules`) — что показывать в каталоге, какие есть
   категории, статус, порядок сортировки. Это управляет и backend, и
   frontend через `/api/v1/modules`.
2. **Frontend component registry** (`frontend/src/modules/registry.tsx`) —
   какой React-компонент открывать по `module_key`. Единственное место,
   где Core "знает" о конкретных модулях.

## Пошагово

1. **Создать папку модуля**
   `frontend/src/modules/<module-key>/`

2. **Реализовать entry point**
   Один React-компонент, например `NexaFilesPage.tsx`. Модуль получает
   контекст через обычные hooks (`useCurrentUser`, `useModules` и т.д.) —
   отдельного `ModuleContext` API пока нет (см. "Будущее" ниже), но
   заложено архитектурно (п.60 спецификации).

3. **Зарегистрировать модуль в базе данных**
   Новая SQL-миграция (не редактировать `0001`/`0002`!):

   ```sql
   -- migrations/000N_nexa_add_<module-key>.sql
   insert into nexa_modules (module_key, name, slug, description, category, icon, route, version, status, sort_order)
   values ('nexa-files', 'NexaFiles', 'nexa-files', 'Инструменты для работы с файлами.', 'files', 'files', '/apps/nexa-files', '1.0.0', 'active', 10)
   on conflict (module_key) do nothing;
   ```

   Применить через Supabase SQL Editor (см. `docs/MANUAL_STEPS.md`).

4. **Добавить permissions** (если модулю нужны специфичные права —
   сейчас достаточно `module.view`/`module.use` на уровне
   `nexa_user_modules.is_enabled`; сложный RBAC не нужен, см. п.61
   спецификации).

5. **Добавить route в component registry**

   ```ts
   // frontend/src/modules/registry.tsx
   export const MODULE_COMPONENTS = {
     "codenexa-demo": lazy(() => import("./demo/DemoModulePage").then(m => ({ default: m.DemoModulePage }))),
     "nexa-files": lazy(() => import("./nexa-files/NexaFilesPage").then(m => ({ default: m.NexaFilesPage }))), // ← новая строка
   };
   ```

   Это единственная строка, которую нужно добавить в Core. `ModuleRoutePage`
   (`frontend/src/features/moduleRoute/ModuleRoutePage.tsx`) сам подхватит
   и смонтирует компонент по `route: "/apps/nexa-files"`.

6. **Добавить тесты**
   `frontend/src/modules/nexa-files/__tests__/` — минимум: рендерится без
   ошибок, основной happy-path. Backend-специфичную логику модуля (если
   есть собственные API-роуты) — в `tests/backend/`.

7. **Проверить registry**
   `getModuleComponent("nexa-files")` должен вернуть компонент, а не `null`
   (по аналогии с `frontend/src/modules/__tests__/registry.test.ts`).

8. **Build**
   `cd frontend && npm run build` — новый модуль должен попасть в
   отдельный чанк (lazy loading, п.39), проверить в выводе `vite build`.

9. **Deploy**
   Обычный git push → Railway пересоберёт frontend и backend (если модуль
   принёс свои API-роуты — добавить их как `app/routers/<module>.py` и
   зарегистрировать в `app/server.py`, тем же способом, каким
   зарегистрированы роутеры Core).

## Что Core модулю не должен передавать

Модуль получает данные через обычные общие hooks (`useCurrentUser`,
`useModules`, `useFavorites` и т.д.) и через свои собственные API-роуты,
если они есть. Модуль **не должен**:
- иметь прямой доступ к таблицам других модулей;
- получать `service_role`/секреты через frontend;
- переопределять поведение Core-навигации.

## Будущее: `ModuleContext`

Спецификация (п.60) предусматривает выделенный `ModuleContext`
(`currentUser`, `theme`, `locale`, `navigation`, `notifications`,
`favorites`, `analytics/events`) как единый API для модулей вместо прямого
использования hooks Core. В Core v1 это не реализовано (не хотим
overengineering на пустом месте — п.56), но текущая структура
(`frontend/src/hooks/*`) уже устроена так, что обернуть их в
`ModuleContext.Provider` в будущем можно без изменения самих hooks.

## Удаление demo-модуля

Когда архитектура проверена и `codenexa-demo` больше не нужен:

```sql
delete from nexa_modules where module_key = 'codenexa-demo';
```

и удалить строку `"codenexa-demo": lazy(...)` из
`frontend/src/modules/registry.tsx` + папку `frontend/src/modules/demo/`.
Каскадные `nexa_user_modules`/`nexa_favorites`/`nexa_history` удалятся
автоматически (FK `on delete cascade` / `on delete set null`).
