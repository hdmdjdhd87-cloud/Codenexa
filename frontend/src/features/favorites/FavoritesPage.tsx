import { Link } from "react-router-dom";
import t from "@/i18n";
import { useFavorites } from "@/hooks/useFavorites";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";

export function FavoritesPage() {
  const favorites = useFavorites();

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-cn-2xl font-semibold mb-4">{t("nav.favorites")}</h1>

      {favorites.isLoading && <LoadingState />}
      {favorites.isError && <ErrorState message={t("errors.loadFavorites")} onRetry={() => favorites.refetch()} />}
      {favorites.data && favorites.data.length === 0 && <EmptyState title={t("empty.favorites")} />}
      {favorites.data && favorites.data.length > 0 && (
        <div className="flex flex-col gap-2.5">
          {favorites.data.map((f) => (
            <Link
              key={f.id}
              to={`/apps/${f.module_key}`}
              className="rounded-2xl bg-surface border border-border p-4 flex items-center gap-3 active:scale-[0.98] transition-transform"
            >
              <div className="w-11 h-11 shrink-0 rounded-xl bg-surface-elevated border border-border flex items-center justify-center text-accent font-semibold text-[15px]">
                {f.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-text-primary font-semibold text-cn-md truncate">{f.name}</p>
                {f.description && <p className="text-text-secondary text-cn-sm truncate">{f.description}</p>}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
