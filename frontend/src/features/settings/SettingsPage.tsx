import t from "@/i18n";
import { useSettings } from "@/hooks/useSettings";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { haptic } from "@/lib/telegram";

export function SettingsPage() {
  const settings = useSettings();

  if (settings.isLoading) return <LoadingState />;
  if (settings.isError || !settings.data) {
    return <ErrorState message={t("errors.loadSettings")} onRetry={() => settings.refetch()} />;
  }

  const s = settings.data;

  function toggle(field: "haptic_feedback" | "notifications_enabled") {
    haptic("light");
    settings.update.mutate({ [field]: !s[field] });
  }

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-[20px] font-semibold mb-4">{t("settings.title")}</h1>

      <div className="rounded-2xl bg-surface border border-border divide-y divide-border">
        <RowStatic label={t("settings.language")} value="Русский" />
        <RowStatic
          label={t("settings.theme")}
          value={
            s.theme === "dark" ? t("settings.themeDark") : s.theme === "light" ? t("settings.themeLight") : t("settings.themeSystem")
          }
        />
        <RowToggle label={t("settings.haptics")} checked={s.haptic_feedback} onChange={() => toggle("haptic_feedback")} />
        <RowToggle
          label={t("settings.notifications")}
          checked={s.notifications_enabled}
          onChange={() => toggle("notifications_enabled")}
        />
      </div>
    </div>
  );
}

function RowStatic({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-text-primary text-[13.5px]">{label}</span>
      <span className="text-text-secondary text-[13px]">{value}</span>
    </div>
  );
}

function RowToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-text-primary text-[13.5px]">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={onChange}
        className={`w-11 h-6 rounded-full relative transition-colors ${checked ? "bg-accent" : "bg-border"}`}
      >
        <span
          className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
            checked ? "translate-x-[22px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}
