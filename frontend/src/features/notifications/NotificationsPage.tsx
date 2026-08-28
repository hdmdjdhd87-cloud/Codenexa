import t from "@/i18n";
import { useNotifications } from "@/hooks/useNotifications";
import { PageShell } from "@/components/PageShell";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";

export function NotificationsPage() {
  const notifications = useNotifications();

  return (
    <PageShell
      title={t("notifications.title")}
      action={
        notifications.data &&
        notifications.data.some((n) => !n.is_read) && (
          <button onClick={() => notifications.markAllRead.mutate()} className="text-cn-sm font-semibold text-accent">
            {t("notifications.markAllRead")}
          </button>
        )
      }
    >
      {notifications.isLoading && <LoadingState />}
      {notifications.isError && (
        <ErrorState message={t("errors.loadNotifications")} onRetry={() => notifications.refetch()} />
      )}
      {notifications.data && notifications.data.length === 0 && <EmptyState title={t("empty.notifications")} />}
      {notifications.data && notifications.data.length > 0 && (
        <div className="flex flex-col gap-2">
          {notifications.data.map((n) => (
            <button
              key={n.id}
              onClick={() => !n.is_read && notifications.markRead.mutate(n.id)}
              className={`text-left rounded-xl border px-4 py-3 ${
                n.is_read ? "bg-surface border-border" : "bg-accent/10 border-accent/30"
              }`}
            >
              <p className="text-text-primary text-cn-base font-semibold">{n.title}</p>
              <p className="text-text-secondary text-cn-sm mt-0.5">{n.message}</p>
            </button>
          ))}
        </div>
      )}
    </PageShell>
  );
}
