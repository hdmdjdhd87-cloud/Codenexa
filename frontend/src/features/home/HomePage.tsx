import { Link } from "react-router-dom";
import t from "@/i18n";
import { useModules } from "@/hooks/useModules";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useHistory } from "@/hooks/useHistory";
import { useNotifications } from "@/hooks/useNotifications";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleCard } from "@/components/ModuleCard";
import { Avatar } from "@/components/Avatar";
import { useFavorites } from "@/hooks/useFavorites";

function greetingByHour(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return t("home.greetingMorning");
  if (h >= 12 && h < 18) return t("home.greetingDay");
  if (h >= 18 && h < 23) return t("home.greetingEvening");
  return t("home.greetingNight");
}

function formatRecentTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return sameDay ? `Сегодня, ${time}` : `${d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" })}, ${time}`;
}

export function HomePage() {
  const { data: user } = useCurrentUser();
  const modules = useModules();
  const favorites = useFavorites();
  const history = useHistory();
  const notifications = useNotifications();

  const unreadCount = (notifications.data ?? []).filter((n) => !n.is_read).length;

  const displayName = user?.first_name || t("home.welcomeFallback");
  const favoriteIds = new Set((favorites.data ?? []).map((f) => f.module_id));

  const lastOpened = (history.data ?? []).find((h) => h.action === "module_open" && h.module_name && h.module_key);

  return (
    <div className="px-4 pt-5 pb-6">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="text-text-secondary text-[13px]">{greetingByHour()}</p>
          <h1 className="text-text-primary text-[22px] font-semibold mt-0.5 truncate">
            {displayName} {user ? "👋" : ""}
          </h1>
          {user?.username && <p className="text-text-secondary text-[13px] mt-0.5">@{user.username}</p>}
        </div>
        {user && (
          <div className="flex items-center gap-2 shrink-0">
            <Link to="/notifications" aria-label={t("notifications.title")} className="relative w-10 h-10 rounded-xl bg-surface border border-border flex items-center justify-center">
              <span aria-hidden="true">🔔</span>
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-error text-white text-[9px] font-bold flex items-center justify-center">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Link>
            <Avatar photoUrl={user.photo_url} name={displayName} size={48} />
          </div>
        )}
      </div>

      <section className="mt-6 rounded-2xl bg-surface-elevated border border-border p-5">
        <h2 className="text-text-primary text-[17px] font-semibold">{t("home.heroTitle")}</h2>
        <p className="text-text-secondary text-[13px] mt-1">{t("home.heroSubtitle")}</p>
      </section>

      {lastOpened && (
        <section className="mt-5">
          <h3 className="text-text-primary text-[14px] font-semibold mb-2.5">{t("home.lastModule")}</h3>
          <Link
            to={`/apps/${lastOpened.module_key}`}
            className="rounded-2xl bg-surface border border-border p-4 flex items-center justify-between"
          >
            <div className="min-w-0">
              <p className="text-text-primary font-semibold text-[14px] truncate">{lastOpened.module_name}</p>
              <p className="text-text-secondary text-[12px] mt-0.5">{formatRecentTime(lastOpened.created_at)}</p>
            </div>
            <span className="text-accent text-[12.5px] font-semibold shrink-0 ml-3">{t("common.open")}</span>
          </Link>
        </section>
      )}

      <section className="mt-6">
        <h3 className="text-text-primary text-[15px] font-semibold mb-3">{t("home.yourApps")}</h3>

        {modules.isLoading && <LoadingState />}
        {modules.isError && (
          <ErrorState message={t("errors.loadModules")} onRetry={() => modules.refetch()} />
        )}
        {modules.data && modules.data.length === 0 && (
          <EmptyState
            title={t("empty.modules")}
            action={
              <Link
                to="/catalog"
                className="px-5 py-2.5 rounded-xl bg-accent text-white text-[13px] font-semibold inline-block"
              >
                {t("home.openCatalog")}
              </Link>
            }
          />
        )}
        {modules.data && modules.data.length > 0 && (
          <div className="flex flex-col gap-2.5">
            {modules.data.slice(0, 5).map((m) => (
              <ModuleCard key={m.id} module={m} isFavorite={favoriteIds.has(m.id)} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
