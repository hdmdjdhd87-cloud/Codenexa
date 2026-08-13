-- ============================================================
-- CodeNexa System — Core migration 0001
-- Создаёт ТОЛЬКО таблицы с префиксом nexa_.
-- НЕ изменяет и не трогает существующие таблицы старого проекта:
-- admin_users, audit_log, blocked_slots, booking_attempts, bookings,
-- breaks, reviews, services, settings, working_hours и любые другие.
--
-- Применять вручную через Supabase SQL Editor (Project → SQL Editor).
-- Скрипт идемпотентен: использует IF NOT EXISTS, безопасно перезапускать.
-- ============================================================

create extension if not exists "pgcrypto"; -- для gen_random_uuid()

-- ------------------------------------------------------------
-- nexa_users — пользователи, авторизованные через Telegram
-- ------------------------------------------------------------
create table if not exists nexa_users (
  id               uuid primary key default gen_random_uuid(),
  telegram_user_id bigint not null unique,
  username         text,
  first_name       text,
  last_name        text,
  language_code    text,
  photo_url        text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  last_seen_at     timestamptz
);
create index if not exists idx_nexa_users_telegram_user_id on nexa_users (telegram_user_id);

-- ------------------------------------------------------------
-- nexa_modules — реестр модулей/продуктов экосистемы (registry-driven)
-- ------------------------------------------------------------
create table if not exists nexa_modules (
  id           uuid primary key default gen_random_uuid(),
  module_key   text not null unique,
  name         text not null,
  slug         text not null,
  description  text,
  category     text,
  icon         text,
  route        text,
  version      text not null default '1.0.0',
  status       text not null default 'active'
               check (status in ('active','disabled','maintenance')),
  is_featured  boolean not null default false,
  sort_order   integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_nexa_modules_module_key on nexa_modules (module_key);
create index if not exists idx_nexa_modules_category on nexa_modules (category);
create index if not exists idx_nexa_modules_status on nexa_modules (status);

-- ------------------------------------------------------------
-- nexa_user_modules — связь пользователь↔модуль (подключение, доступ)
-- ------------------------------------------------------------
create table if not exists nexa_user_modules (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references nexa_users(id) on delete cascade,
  module_id   uuid not null references nexa_modules(id) on delete cascade,
  is_favorite boolean not null default false,
  is_enabled  boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, module_id)
);
create index if not exists idx_nexa_user_modules_user_id on nexa_user_modules (user_id);
create index if not exists idx_nexa_user_modules_module_id on nexa_user_modules (module_id);

-- ------------------------------------------------------------
-- nexa_favorites — избранные модули (отдельно от nexa_user_modules
-- по требованию спецификации: быстрая, независимая выборка избранного)
-- ------------------------------------------------------------
create table if not exists nexa_favorites (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references nexa_users(id) on delete cascade,
  module_id  uuid not null references nexa_modules(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, module_id)
);
create index if not exists idx_nexa_favorites_user_id on nexa_favorites (user_id);
create index if not exists idx_nexa_favorites_module_id on nexa_favorites (module_id);

-- ------------------------------------------------------------
-- nexa_projects — пользовательские пространства/проекты (задел на будущее)
-- ------------------------------------------------------------
create table if not exists nexa_projects (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references nexa_users(id) on delete cascade,
  name        text not null,
  description text,
  icon        text,
  accent      text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_nexa_projects_user_id on nexa_projects (user_id);

-- ------------------------------------------------------------
-- nexa_history — реальные действия пользователя (создаются backend-событиями)
-- ------------------------------------------------------------
create table if not exists nexa_history (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references nexa_users(id) on delete cascade,
  module_id  uuid references nexa_modules(id) on delete set null,
  action     text not null,
  metadata   jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_nexa_history_user_id on nexa_history (user_id);
create index if not exists idx_nexa_history_created_at on nexa_history (created_at desc);

-- ------------------------------------------------------------
-- nexa_notifications — уведомления
-- ------------------------------------------------------------
create table if not exists nexa_notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references nexa_users(id) on delete cascade,
  type       text not null,
  title      text not null,
  message    text not null,
  module_id  uuid references nexa_modules(id) on delete set null,
  is_read    boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists idx_nexa_notifications_user_id on nexa_notifications (user_id);
create index if not exists idx_nexa_notifications_is_read on nexa_notifications (is_read);
create index if not exists idx_nexa_notifications_created_at on nexa_notifications (created_at desc);

-- ------------------------------------------------------------
-- nexa_settings — настройки пользователя (1:1 с nexa_users)
-- ------------------------------------------------------------
create table if not exists nexa_settings (
  id                     uuid primary key default gen_random_uuid(),
  user_id                uuid not null unique references nexa_users(id) on delete cascade,
  language               text not null default 'ru',
  theme                  text not null default 'system'
                         check (theme in ('system','dark','light')),
  haptic_feedback        boolean not null default true,
  notifications_enabled  boolean not null default true,
  settings_json          jsonb not null default '{}'::jsonb,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);
create index if not exists idx_nexa_settings_user_id on nexa_settings (user_id);

-- ------------------------------------------------------------
-- nexa_sessions — НЕ создаётся.
-- Решение (см. п.10 спецификации "не создавать таблицу просто ради
-- таблицы"): авторизация построена на серверной валидации Telegram
-- initData при каждом запросе + краткоживущий подписанный JWT,
-- выдаваемый backend'ом (app/auth/telegram.py). Токен не хранится
-- в БД — он самодостаточен и проверяется по подписи (JWT_SECRET).
-- Если в будущем понадобится server-side revoke/список активных
-- сессий — таблицу можно добавить отдельной миграцией 0002.
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- триггер updated_at (переиспользуемая функция)
-- ------------------------------------------------------------
create or replace function nexa_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  t text;
begin
  foreach t in array array['nexa_users','nexa_modules','nexa_user_modules','nexa_projects','nexa_settings']
  loop
    execute format(
      'drop trigger if exists trg_%1$s_updated_at on %1$s;
       create trigger trg_%1$s_updated_at
       before update on %1$s
       for each row execute function nexa_set_updated_at();',
      t
    );
  end loop;
end $$;
