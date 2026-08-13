import t from "@/i18n";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useFavorites } from "@/hooks/useFavorites";
import { useModules } from "@/hooks/useModules";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function ProfilePage() {
  const user = useCurrentUser();
  const favorites = useFavorites();
  const modules = useModules();

  if (user.isLoading) return <LoadingState />;
  if (user.isError || !user.data) {
    return <ErrorState message={t("errors.loadProfile")} onRetry={() => user.refetch()} />;
  }

  const fullName = [user.data.first_name, user.data.last_name].filter(Boolean).join(" ") || t("home.welcomeFallback");

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("profile.title")}</h1>

      <div className="flex items-center gap-3">
        <div className="w-16 h-16 rounded-2xl bg-surface-elevated border border-border flex items-center justify-center text-accent text-[22px] font-semibold overflow-hidden">
          {user.data.photo_url ? (
            <img src={user.data.photo_url} alt="" className="w-full h-full object-cover" />
          ) : (
            fullName.charAt(0).toUpperCase()
          )}
        </div>
        <div className="min-w-0">
          <p className="text-text-primary font-semibold text-[16px] truncate">{fullName}</p>
          {user.data.username && <p className="text-text-secondary text-[13px]">@{user.data.username}</p>}
        </div>
      </div>

      <div className="mt-6 rounded-2xl bg-surface border border-border divide-y divide-border">
        <Row label={t("profile.joined")} value={formatDate(user.data.created_at)} />
        <Row label={t("profile.appsCount")} value={String(modules.data?.length ?? 0)} />
        <Row label={t("profile.favoritesCount")} value={String(favorites.data?.length ?? 0)} />
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
