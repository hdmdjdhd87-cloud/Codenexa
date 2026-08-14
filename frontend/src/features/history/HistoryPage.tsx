import t from "@/i18n";
import { useHistory } from "@/hooks/useHistory";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import type { HistoryItem } from "@/types";

const ACTION_LABELS: Record<string, string> = {
  module_open: "Открыто",
  favorite_add: "Добавлено в избранное",
  favorite_remove: "Убрано из избранного",
};

function actionLabel(item: HistoryItem): string {
  return ACTION_LABELS[item.action] ?? item.action;
}

function timeOnly(iso: string): string {
  return new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function groupByDay(items: HistoryItem[]) {
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();

  const groups: { label: string; items: HistoryItem[] }[] = [
    { label: "Сегодня", items: [] },
    { label: "Вчера", items: [] },
    { label: "Ранее", items: [] },
  ];

  for (const item of items) {
    const d = new Date(item.created_at).toDateString();
    if (d === today) groups[0].items.push(item);
    else if (d === yesterday) groups[1].items.push(item);
    else groups[2].items.push(item);
  }

  return groups.filter((g) => g.items.length > 0);
}

export function HistoryPage() {
  const history = useHistory();

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("history.title")}</h1>

      {history.isLoading && <LoadingState />}
      {history.isError && <ErrorState message={t("errors.loadHistory")} onRetry={() => history.refetch()} />}
      {history.data && history.data.length === 0 && (
        <EmptyState title={t("empty.history")} description="Здесь появятся открытые приложения и действия." />
      )}
      {history.data && history.data.length > 0 && (
        <div className="flex flex-col gap-5">
          {groupByDay(history.data).map((group) => (
            <div key={group.label}>
              <p className="text-text-secondary text-[12px] font-semibold uppercase tracking-wide mb-2">
                {group.label}
              </p>
              <div className="flex flex-col gap-2">
                {group.items.map((item) => (
                  <div key={item.id} className="rounded-xl bg-surface border border-border px-4 py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-text-primary text-[13.5px] font-medium truncate">
                        {item.module_name ?? actionLabel(item)}
                      </p>
                      {item.module_name && (
                        <p className="text-text-secondary text-[11.5px] mt-0.5">{actionLabel(item)}</p>
                      )}
                    </div>
                    <span className="text-text-secondary text-[11.5px] shrink-0">{timeOnly(item.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
