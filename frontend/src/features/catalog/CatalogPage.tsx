import { useMemo, useState } from "react";
import t from "@/i18n";
import { useModules } from "@/hooks/useModules";
import { useFavorites } from "@/hooks/useFavorites";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { ModuleListSkeleton } from "@/components/states/Skeleton";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleCard } from "@/components/ModuleCard";

export function CatalogPage() {
  const modules = useModules();
  const favorites = useFavorites();
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 250);
  const [category, setCategory] = useState<string>("all");

  const favoriteIds = new Set((favorites.data ?? []).map((f) => f.module_id));

  const categories = useMemo(() => {
    if (!modules.data) return [];
    const set = new Set(modules.data.map((m) => m.category).filter(Boolean) as string[]);
    return Array.from(set);
  }, [modules.data]);

  const filtered = useMemo(() => {
    if (!modules.data) return [];
    return modules.data.filter((m) => {
      const matchesCategory = category === "all" || m.category === category;
      const matchesQuery =
        debouncedQuery.trim() === "" || m.name.toLowerCase().includes(debouncedQuery.trim().toLowerCase());
      return matchesCategory && matchesQuery;
    });
  }, [modules.data, category, debouncedQuery]);

  function toggleFavorite(moduleId: string) {
    if (favoriteIds.has(moduleId)) favorites.remove.mutate(moduleId);
    else favorites.add.mutate(moduleId);
  }

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-cn-2xl font-semibold mb-4">{t("catalog.title")}</h1>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("catalog.searchPlaceholder")}
        className="w-full rounded-xl bg-surface border border-border px-4 py-2.5 text-cn-md text-text-primary placeholder:text-text-secondary outline-none focus:border-accent"
      />

      {categories.length > 0 && (
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1 -mx-4 px-4">
          <button
            onClick={() => setCategory("all")}
            className={`shrink-0 px-3.5 py-1.5 rounded-full text-cn-sm font-medium border ${
              category === "all" ? "bg-accent text-white border-accent" : "bg-surface text-text-secondary border-border"
            }`}
          >
            {t("common.all")}
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-cn-sm font-medium border ${
                category === c ? "bg-accent text-white border-accent" : "bg-surface text-text-secondary border-border"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      )}

      <div className="mt-4">
        {modules.isLoading && <ModuleListSkeleton />}
        {modules.isError && <ErrorState message={t("errors.loadModules")} onRetry={() => modules.refetch()} />}
        {modules.data && filtered.length === 0 && <EmptyState title={t("empty.modules")} />}
        {modules.data && filtered.length > 0 && (
          <div className="flex flex-col gap-2.5">
            {filtered.map((m) => (
              <ModuleCard key={m.id} module={m} isFavorite={favoriteIds.has(m.id)} onToggleFavorite={toggleFavorite} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
