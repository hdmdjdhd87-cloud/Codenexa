import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { adminService, type AdminUser } from "@/services/adminService";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { haptic } from "@/lib/telegram";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";

type Tab = "dashboard" | "users" | "audit";

const ACTION_LABELS: Record<string, string> = {
  "user.block": "Заблокирован пользователь",
  "user.unblock": "Разблокирован пользователь",
  "user.revoke_sessions": "Отозваны сессии",
};

export function AdminPage() {
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["admin", "me"], queryFn: () => adminService.me() });
  const [tab, setTab] = useState<Tab>("dashboard");

  if (me.isLoading) {
    return (
      <div className="px-4 pt-5 pb-6">
        <LoadingState />
      </div>
    );
  }

  if (me.isError) {
    return (
      <div className="px-4 pt-5 pb-6">
        <ErrorState message="Не удалось проверить права доступа." onRetry={() => me.refetch()} />
      </div>
    );
  }

  if (!me.data?.is_admin) {
    // Намеренно не 403-страница с объяснениями "у вас нет доступа" —
    // обычный пользователь в принципе не должен знать, что /admin
    // существует как отдельная концепция. Просто отправляем домой.
    navigate("/", { replace: true });
    return null;
  }

  return (
    <div className="px-4 pt-5 pb-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-text-primary text-[20px] font-semibold">Админ-панель</h1>
        <span className="text-[11px] text-text-secondary bg-surface-elevated border border-border rounded-full px-2.5 py-1">
          {me.data.role_name}
        </span>
      </div>
      <p className="text-text-secondary text-[13px] mb-5">Доступные права: {me.data.permissions?.join(", ")}</p>

      <div className="flex gap-1.5 mb-5 bg-surface-elevated rounded-xl p-1">
        {(
          [
            ["dashboard", "Обзор"],
            ["users", "Пользователи"],
            ["audit", "Журнал"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 py-2 rounded-lg text-[12.5px] font-semibold transition-colors ${
              tab === key ? "bg-accent text-white" : "text-text-secondary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "users" && <UsersTab permissions={me.data.permissions ?? []} />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

/* ============================= DASHBOARD ============================= */

function DashboardTab() {
  const dashboard = useQuery({ queryKey: ["admin", "dashboard"], queryFn: () => adminService.dashboard() });

  if (dashboard.isLoading) return <LoadingState />;
  if (dashboard.isError || !dashboard.data) {
    return <ErrorState message="Не удалось загрузить обзор." onRetry={() => dashboard.refetch()} />;
  }

  const d = dashboard.data;
  const cards: [string, number | string, string][] = [
    ["Пользователей всего", d.total_users, "text-text-primary"],
    ["Заблокировано", d.blocked_users, d.blocked_users > 0 ? "text-error" : "text-text-primary"],
    ["Документов", d.total_documents, "text-text-primary"],
    ["Активных ссылок", d.active_shares, "text-text-primary"],
    ["Rate-limit окон за час", d.rate_limit_windows_last_hour, "text-text-primary"],
  ];

  return (
    <div className="grid grid-cols-2 gap-2.5">
      {cards.map(([label, value, color]) => (
        <div key={label} className="rounded-xl bg-surface border border-border p-3.5">
          <p className={`text-[22px] font-semibold ${color}`}>{value}</p>
          <p className="text-text-secondary text-[11.5px] mt-1">{label}</p>
        </div>
      ))}
    </div>
  );
}

/* ============================= USERS ============================= */

function UsersTab({ permissions }: { permissions: string[] }) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  const users = useQuery({
    queryKey: ["admin", "users", debouncedSearch],
    queryFn: () => adminService.users(debouncedSearch || undefined),
  });

  const canBlock = permissions.includes("users.block");
  const canRevoke = permissions.includes("users.revoke_sessions");

  if (selectedUser) {
    return (
      <UserDetail
        user={selectedUser}
        canBlock={canBlock}
        canRevoke={canRevoke}
        onBack={() => setSelectedUser(null)}
        onUpdated={(u) => setSelectedUser(u)}
      />
    );
  }

  return (
    <div>
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Поиск по имени, юзернейму или Telegram ID"
        className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-[13.5px] text-text-primary outline-none focus:border-accent mb-4"
      />

      {users.isLoading && <LoadingState />}
      {users.isError && <ErrorState message="Не удалось загрузить пользователей." onRetry={() => users.refetch()} />}
      {users.data && users.data.length === 0 && (
        <EmptyState title="Никого не нашлось" description="Попробуйте другой запрос." />
      )}

      <div className="flex flex-col gap-1.5">
        {(users.data ?? []).map((u) => (
          <button
            key={u.id}
            onClick={() => setSelectedUser(u)}
            className={`text-left rounded-xl border p-3 flex items-center justify-between gap-2 ${
              u.is_blocked ? "bg-error/5 border-error/30" : "bg-surface border-border"
            }`}
          >
            <div className="min-w-0">
              <p className="text-text-primary text-[13.5px] font-medium truncate">
                {[u.first_name, u.last_name].filter(Boolean).join(" ") || `ID ${u.telegram_user_id}`}
                {u.username && <span className="text-text-secondary font-normal"> · @{u.username}</span>}
              </p>
              <p className="text-text-secondary text-[11.5px] mt-0.5">Telegram ID {u.telegram_user_id}</p>
            </div>
            {u.is_blocked && (
              <span className="shrink-0 text-[10.5px] font-semibold text-error bg-error/10 rounded-full px-2 py-1">
                Заблокирован
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserDetail({
  user,
  canBlock,
  canRevoke,
  onBack,
  onUpdated,
}: {
  user: AdminUser;
  canBlock: boolean;
  canRevoke: boolean;
  onBack: () => void;
  onUpdated: (u: AdminUser) => void;
}) {
  const qc = useQueryClient();
  const [blockReason, setBlockReason] = useState("");
  const [confirmingBlock, setConfirmingBlock] = useState(false);
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const block = useMutation({
    mutationFn: (reason: string) => adminService.blockUser(user.id, reason),
    onSuccess: (updated) => {
      haptic("success");
      setNotice("Пользователь заблокирован.");
      setConfirmingBlock(false);
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      onUpdated({ ...user, ...updated });
    },
  });

  const unblock = useMutation({
    mutationFn: () => adminService.unblockUser(user.id),
    onSuccess: (updated) => {
      haptic("success");
      setNotice("Пользователь разблокирован.");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      onUpdated({ ...user, ...updated });
    },
  });

  const revoke = useMutation({
    mutationFn: () => adminService.revokeSessions(user.id),
    onSuccess: () => {
      haptic("success");
      setNotice("Все сессии отозваны — при следующем открытии Mini App потребуется повторный вход.");
      setConfirmingRevoke(false);
    },
  });

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 text-accent text-[13px] font-semibold mb-4">
        <ArrowLeft size={16} aria-hidden="true" /> К списку
      </button>

      <div className="rounded-xl bg-surface border border-border p-4 mb-4">
        <p className="text-text-primary text-[16px] font-semibold">
          {[user.first_name, user.last_name].filter(Boolean).join(" ") || `ID ${user.telegram_user_id}`}
        </p>
        {user.username && <p className="text-text-secondary text-[13px] mt-0.5">@{user.username}</p>}
        <p className="text-text-secondary text-[12px] mt-2">Telegram ID: {user.telegram_user_id}</p>
        <p className="text-text-secondary text-[12px]">Регистрация: {formatDate(user.created_at)}</p>
        {user.is_blocked && (
          <p className="text-error text-[12.5px] mt-2 font-medium">
            Заблокирован{user.blocked_reason ? `: ${user.blocked_reason}` : ""}
          </p>
        )}
      </div>

      {notice && <p className="text-success text-[12.5px] mb-3">{notice}</p>}

      {canBlock && (
        <div className="mb-3">
          {!user.is_blocked ? (
            confirmingBlock ? (
              <div className="rounded-xl bg-surface border border-border p-3.5">
                <input
                  value={blockReason}
                  onChange={(e) => setBlockReason(e.target.value)}
                  placeholder="Причина блокировки"
                  className="w-full rounded-lg bg-surface-elevated border border-border px-3 py-2 text-[13px] text-text-primary outline-none focus:border-accent mb-2.5"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => block.mutate(blockReason || "Не указана")}
                    disabled={block.isPending}
                    className="flex-1 py-2 rounded-lg bg-error/15 text-error text-[12.5px] font-semibold disabled:opacity-60"
                  >
                    {block.isPending ? "Блокируем…" : "Подтвердить блокировку"}
                  </button>
                  <button
                    onClick={() => setConfirmingBlock(false)}
                    className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setConfirmingBlock(true)}
                className="w-full py-2.5 rounded-xl bg-error/10 border border-error/30 text-error text-[13px] font-semibold"
              >
                Заблокировать пользователя
              </button>
            )
          ) : (
            <button
              onClick={() => unblock.mutate()}
              disabled={unblock.isPending}
              className="w-full py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[13px] font-semibold disabled:opacity-60"
            >
              {unblock.isPending ? "Разблокируем…" : "Разблокировать"}
            </button>
          )}
        </div>
      )}

      {canRevoke && (
        <div>
          {confirmingRevoke ? (
            <div className="rounded-xl bg-surface border border-border p-3.5">
              <p className="text-text-secondary text-[12px] mb-2.5">
                Все уже выданные токены сессии перестанут приниматься. Пользователю понадобится открыть Mini App
                заново — Telegram выдаст новую сессию автоматически.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => revoke.mutate()}
                  disabled={revoke.isPending}
                  className="flex-1 py-2 rounded-lg bg-accent text-white text-[12.5px] font-semibold disabled:opacity-60"
                >
                  {revoke.isPending ? "Отзываем…" : "Подтвердить"}
                </button>
                <button
                  onClick={() => setConfirmingRevoke(false)}
                  className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold"
                >
                  Отмена
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setConfirmingRevoke(true)}
              className="w-full py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[13px] font-semibold"
            >
              Отозвать все сессии
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ============================= AUDIT LOG ============================= */

function AuditTab() {
  const log = useQuery({ queryKey: ["admin", "audit-log"], queryFn: () => adminService.auditLog() });

  if (log.isLoading) return <LoadingState />;
  if (log.isError) return <ErrorState message="Не удалось загрузить журнал." onRetry={() => log.refetch()} />;
  if (!log.data || log.data.length === 0) {
    return <EmptyState title="Журнал пуст" description="Здесь появятся действия администраторов." />;
  }

  return (
    <div className="flex flex-col gap-2">
      {log.data.map((entry) => (
        <div key={entry.id} className="rounded-xl bg-surface border border-border p-3">
          <div className="flex items-center justify-between gap-2 mb-1">
            <p className="text-text-primary text-[13px] font-medium">{ACTION_LABELS[entry.action] ?? entry.action}</p>
            <p className="text-text-secondary text-[11px] shrink-0">{formatDate(entry.created_at)}</p>
          </div>
          <p className="text-text-secondary text-[11.5px]">
            {entry.actor_username ? `@${entry.actor_username}` : `ID ${entry.actor_telegram_id ?? "—"}`}
            {entry.reason ? ` · ${entry.reason}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
