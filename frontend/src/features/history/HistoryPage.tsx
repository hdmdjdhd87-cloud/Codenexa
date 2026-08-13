import t from "@/i18n";
import { useHistory } from "@/hooks/useHistory";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
}

export function HistoryPage() {
  const history = useHistory();

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("history.title")}</h1>

      {history.isLoading && <LoadingState />}
      {history.isError && <ErrorState message={t("errors.loadHistory")} onRetry={() => history.refetch()} />}
      {history.data && history.data.length === 0 && <EmptyState title={t("empty.history")} />}
      {history.data && history.data.length > 0 && (
        <div className="flex flex-col gap-2">
          {history.data.map((item) => (
            <div key={item.id} className="rounded-xl bg-surface border border-border px-4 py-3">
              <p className="text-text-primary text-[13.5px] font-medium">
                {item.action}
                {item.module_name ? ` · ${item.module_name}` : ""}
              </p>
              <p className="text-text-secondary text-[11.5px] mt-0.5">{formatDate(item.created_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
