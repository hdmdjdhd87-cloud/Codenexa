import { useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import t from "@/i18n";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useFavorites } from "@/hooks/useFavorites";
import { useModules } from "@/hooks/useModules";
import { useHistory } from "@/hooks/useHistory";
import { useQuery } from "@tanstack/react-query";
import { adminService } from "@/services/adminService";
import { ProfileHeaderSkeleton } from "@/components/states/Skeleton";
import { ErrorState } from "@/components/states/ErrorState";
import { Avatar } from "@/components/Avatar";
import { clearStoredToken } from "@/lib/tokenStorage";
import { closeMiniApp, haptic } from "@/lib/telegram";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function ProfilePage() {
  const user = useCurrentUser();
  const favorites = useFavorites();
  const modules = useModules();
  const history = useHistory();
  const [confirmingLogout, setConfirmingLogout] = useState(false);
  // Тихая проверка: не 403-страница "нет доступа" для обычных
  // пользователей — ссылка на админку просто не существует для них,
  // они не должны знать, что admin-функциональность вообще есть.
  const adminMe = useQuery({ queryKey: ["admin", "me"], queryFn: () => adminService.me(), retry: false });

  if (user.isLoading) {
    return (
      <div className="px-4 pt-5 pb-6">
        <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("profile.title")}</h1>
        <ProfileHeaderSkeleton />
      </div>
    );
  }
  if (user.isError || !user.data) {
    return <ErrorState message={t("errors.loadProfile")} onRetry={() => user.refetch()} />;
  }

  const fullName = [user.data.first_name, user.data.last_name].filter(Boolean).join(" ") || t("home.welcomeFallback");
  const openCount = (history.data ?? []).filter((h) => h.action === "module_open").length;

  function handleLogout() {
    haptic("warning");
    clearStoredToken();
    // "Выход" в Mini App концептуально ограничен: Telegram сам передаёт
    // initData при каждом открытии, поэтому полноценного logout как в
    // обычном вебе нет. Реалистичное действие — сбросить локальную
    // сессию и закрыть Mini App; при следующем открытии пользователь
    // авторизуется заново автоматически через Telegram (это ожидаемо
    // и безопасно, initData валидируется заново на backend).
    closeMiniApp();
  }

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("profile.title")}</h1>

      {/* HEADER */}
      <div className="flex items-center gap-3.5">
        <Avatar photoUrl={user.data.photo_url} name={fullName} size={64} />
        <div className="min-w-0">
          <p className="text-text-primary font-semibold text-[17px] truncate">{fullName}</p>
          {user.data.username && <p className="text-text-secondary text-[13px]">@{user.data.username}</p>}
          <span className="inline-block mt-1.5 text-[10.5px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-accent/15 text-accent">
            CodeNexa Free
          </span>
        </div>
      </div>

      {/* MY ACTIVITY */}
      <SectionLabel>Моя активность</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border divide-y divide-border">
        <Row label="Мои приложения" value={String(modules.data?.length ?? 0)} />
        <Row label={t("profile.favoritesCount")} value={String(favorites.data?.length ?? 0)} />
        <Row label="Запусков" value={String(openCount)} />
        <Row label={t("profile.joined")} value={formatDate(user.data.created_at)} />
      </div>

      {/* SUBSCRIPTION (mock) */}
      <SectionLabel>Тариф</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border p-4">
        <div className="flex items-center justify-between">
          <p className="text-text-primary font-semibold text-[14px]">CodeNexa Free</p>
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-warning/15 text-warning">
            Demo
          </span>
        </div>
        <p className="text-text-secondary text-[12.5px] mt-1.5">
          Тарифы и оплата ещё не подключены — раздел показывает демонстрационные данные, чтобы место в
          интерфейсе было готово к будущей интеграции.
        </p>
        <div className="mt-3.5 pt-3.5 border-t border-border flex flex-col gap-2">
          <LimitBar label="Приложения" used={modules.data?.length ?? 0} total={5} />
          <LimitBar label="Избранное" used={favorites.data?.length ?? 0} total={10} />
        </div>
        <p className="text-text-secondary/70 text-[11px] mt-2.5">
          Демонстрационные лимиты Free-тарифа. Реальные ограничения появятся вместе с оплатой.
        </p>
      </div>

      {/* SYSTEM */}
      <SectionLabel>Система</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border divide-y divide-border overflow-hidden">
        <LinkRow to="/settings" label={t("settings.title")} />
        {adminMe.data?.is_admin && <LinkRow to="/admin" label="Админ-панель" />}
        {!confirmingLogout ? (
          <button
            onClick={() => setConfirmingLogout(true)}
            className="w-full text-left px-4 py-3 text-[13.5px] font-medium text-error"
          >
            Выйти
          </button>
        ) : (
          <div className="px-4 py-3">
            <p className="text-text-secondary text-[12.5px] mb-2.5">
              Приложение закроется, при следующем запуске вы авторизуетесь автоматически через Telegram.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleLogout}
                className="flex-1 py-2 rounded-lg bg-error/15 text-error text-[12.5px] font-semibold"
              >
                Подтвердить
              </button>
              <button
                onClick={() => setConfirmingLogout(false)}
                className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-text-secondary text-[12px] font-semibold uppercase tracking-wide mt-6 mb-2">{children}</p>;
}

function LimitBar({ label, used, total }: { label: string; used: number; total: number }) {
  const pct = Math.min(100, Math.round((used / total) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-[11.5px] mb-1">
        <span className="text-text-secondary">{label}</span>
        <span className="text-text-secondary">{used} / {total}</span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-elevated overflow-hidden">
        <div className="h-full bg-accent rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-text-secondary text-[13px]">{label}</span>
      <span className="text-text-primary text-[13px] font-medium">{value}</span>
    </div>
  );
}

function LinkRow({ to, label }: { to: string; label: string }) {
  return (
    <RouterLink to={to} className="flex items-center justify-between px-4 py-3 text-[13.5px] font-medium text-text-primary">
      <span>{label}</span>
      <span className="text-text-secondary"><ChevronRight size={18} aria-hidden="true" /></span>
    </RouterLink>
  );
}
