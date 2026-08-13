import { Link } from "react-router-dom";
import t from "@/i18n";
import { useModules } from "@/hooks/useModules";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleCard } from "@/components/ModuleCard";
import { useFavorites } from "@/hooks/useFavorites";

function greetingByHour(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return t("home.greetingMorning");
  if (h >= 12 && h < 18) return t("home.greetingDay");
  if (h >= 18 && h < 23) return t("home.greetingEvening");
  return t("home.greetingNight");
}

export function HomePage() {
  const { data: user } = useCurrentUser();
  const modules = useModules();
  const favorites = useFavorites();

  const name = user?.first_name || t("home.welcomeFallback");
  const favoriteIds = new Set((favorites.data ?? []).map((f) => f.module_id));

  return (
    <div className="px-4 pt-5 pb-6">
      <p className="text-text-secondary text-[13px]">{greetingByHour()}</p>
      <h1 className="text-text-primary text-[22px] font-semibold mt-0.5">{name}</h1>

      <section className="mt-6 rounded-2xl bg-surface-elevated border border-border p-5">
        <h2 className="text-text-primary text-[17px] font-semibold">{t("home.heroTitle")}</h2>
        <p className="text-text-secondary text-[13px] mt-1">{t("home.heroSubtitle")}</p>
      </section>

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
