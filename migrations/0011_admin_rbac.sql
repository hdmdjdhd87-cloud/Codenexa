-- ============================================================
-- CodeNexa System — Core migration 0011
-- Admin RBAC (P0-10 / SEC-004 из production-аудита 22.08.2026).
-- Аудит прямо запрещает делать admin через
-- `if telegram_user_id == <hardcoded>` в роутерах — вместо этого
-- полноценная схема ролей/прав + immutable audit log.
-- ============================================================

-- ------------------------------------------------------------
-- admin_roles — фиксированный набор ролей (owner/security_admin/
-- operator/support/content_admin), см. аудит п.14.
-- ------------------------------------------------------------
create table if not exists admin_roles (
  id          uuid primary key default gen_random_uuid(),
  key         text not null unique check (key in ('owner', 'security_admin', 'operator', 'support', 'content_admin')),
  name        text not null,
  created_at  timestamptz not null default now()
);

insert into admin_roles (key, name) values
  ('owner', 'Владелец'),
  ('security_admin', 'Администратор безопасности'),
  ('operator', 'Оператор'),
  ('support', 'Поддержка'),
  ('content_admin', 'Контент-менеджер')
on conflict (key) do nothing;

-- ------------------------------------------------------------
-- admin_permissions — атомарные права. Матрица role->permission
-- ниже в admin_role_permissions, НЕ хардкодится в Python-коде —
-- чтобы права можно было менять без деплоя.
-- ------------------------------------------------------------
create table if not exists admin_permissions (
  id    uuid primary key default gen_random_uuid(),
  key   text not null unique,
  description text not null
);

insert into admin_permissions (key, description) values
  ('users.view',            'Просмотр списка и профилей пользователей'),
  ('users.block',           'Блокировка/разблокировка пользователей'),
  ('users.revoke_sessions', 'Отзыв сессий пользователя'),
  ('documents.view',        'Просмотр метаданных документов (без содержимого)'),
  ('documents.moderate',    'Флаг злоупотребления / жёсткие действия с документами'),
  ('shares.revoke',         'Отзыв публичных ссылок'),
  ('security.view',         'Просмотр security-событий/rate-limit хитов'),
  ('audit.view',            'Просмотр admin_audit_log'),
  ('system.manage',         'Feature flags, maintenance mode, системные настройки'),
  ('admins.manage',         'Назначение/снятие ролей другим админам — только owner')
on conflict (key) do nothing;

-- ------------------------------------------------------------
-- admin_role_permissions — матрица роль -> права.
-- owner получает всё автоматически на уровне кода (см.
-- app/admin/rbac.py), здесь только явные назначения для
-- остальных ролей.
-- ------------------------------------------------------------
create table if not exists admin_role_permissions (
  role_id       uuid not null references admin_roles(id) on delete cascade,
  permission_id uuid not null references admin_permissions(id) on delete cascade,
  primary key (role_id, permission_id)
);

insert into admin_role_permissions (role_id, permission_id)
select r.id, p.id from admin_roles r, admin_permissions p
where r.key = 'security_admin'
  and p.key in ('users.view', 'users.block', 'users.revoke_sessions', 'security.view', 'audit.view', 'shares.revoke')
on conflict do nothing;

insert into admin_role_permissions (role_id, permission_id)
select r.id, p.id from admin_roles r, admin_permissions p
where r.key = 'operator'
  and p.key in ('users.view', 'documents.view', 'shares.revoke', 'security.view')
on conflict do nothing;

insert into admin_role_permissions (role_id, permission_id)
select r.id, p.id from admin_roles r, admin_permissions p
where r.key = 'support'
  and p.key in ('users.view', 'documents.view')
on conflict do nothing;

insert into admin_role_permissions (role_id, permission_id)
select r.id, p.id from admin_roles r, admin_permissions p
where r.key = 'content_admin'
  and p.key in ('documents.view')
on conflict do nothing;

-- ------------------------------------------------------------
-- admin_users — связь nexa_users -> admin_roles. Именно это
-- решает "не хардкодить ID": ID становится seed-данными ОДНОЙ
-- строки в этой таблице, а не веткой if в коде.
-- ------------------------------------------------------------
create table if not exists admin_users (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null unique references nexa_users(id) on delete cascade,
  role_id    uuid not null references admin_roles(id),
  status     text not null default 'active' check (status in ('active', 'suspended')),
  granted_by uuid references admin_users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_admin_users_user_id on admin_users (user_id);

-- ------------------------------------------------------------
-- admin_audit_log — append-only. Приложение не должно иметь
-- UPDATE/DELETE прав на эту таблицу в обычном режиме работы
-- (см. REVOKE ниже) — только INSERT/SELECT.
-- ------------------------------------------------------------
create table if not exists admin_audit_log (
  id               uuid primary key default gen_random_uuid(),
  actor_admin_id   uuid references admin_users(id),
  actor_user_id    uuid references nexa_users(id),
  action           text not null,
  target_type      text,
  target_id        text,
  reason           text,
  before_json      jsonb,
  after_json       jsonb,
  ip_hash          text,
  created_at       timestamptz not null default now()
);
create index if not exists idx_admin_audit_log_created_at on admin_audit_log (created_at);
create index if not exists idx_admin_audit_log_actor on admin_audit_log (actor_admin_id);

-- Append-only на уровне прав: даже с полным доступом к БД через
-- обычную роль приложения UPDATE/DELETE на audit log не даём —
-- сознательно не отзываем у postgres/service_role (им она нужна
-- для восстановления/миграций), но НЕ выдаём отдельную "app-role"
-- с DELETE на эту таблицу, если/когда она появится.
revoke delete, update on admin_audit_log from public;

-- RLS: та же модель, что и в 0010 — backend подключается ролью
-- postgres/service_role (rolbypassrls=true), RLS здесь чисто
-- defense-in-depth на случай будущего прямого PostgREST-доступа.
alter table admin_roles enable row level security;
alter table admin_permissions enable row level security;
alter table admin_role_permissions enable row level security;
alter table admin_users enable row level security;
alter table admin_audit_log enable row level security;

revoke all on admin_roles, admin_permissions, admin_role_permissions, admin_users, admin_audit_log
  from anon, authenticated;

-- ------------------------------------------------------------
-- Bootstrap owner. Аудит подтвердил: telegram_user_id 8129422076
-- уже существует в nexa_users (username CodeNexapremium) — это
-- владелец проекта, назначаем ЕДИНСТВЕННУЮ owner-запись через
-- subquery по telegram_user_id, а не хардкодя uuid и не трогая
-- код роутеров. Идемпотентно (on conflict do nothing по
-- unique(user_id) в admin_users) — безопасно перезапускать.
-- ------------------------------------------------------------
insert into admin_users (user_id, role_id, status)
select u.id, r.id, 'active'
from nexa_users u, admin_roles r
where u.telegram_user_id = 8129422076
  and r.key = 'owner'
on conflict (user_id) do nothing;
