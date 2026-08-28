import { useState } from "react";
import t from "@/i18n";
import { useSettings } from "@/hooks/useSettings";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { haptic } from "@/lib/telegram";
import { clearStoredToken } from "@/lib/tokenStorage";
import { closeMiniApp } from "@/lib/telegram";

export function SettingsPage() {
  const settings = useSettings();
  const [confirmingLogout, setConfirmingLogout] = useState(false);

  if (settings.isLoading) return <LoadingState />;
  if (settings.isError || !settings.data) {
    return <ErrorState message={t("errors.loadSettings")} onRetry={() => settings.refetch()} />;
  }

  const s = settings.data;

  function toggle(field: "haptic_feedback" | "notifications_enabled") {
    haptic("light");
    settings.update.mutate({ [field]: !s[field] });
  }

  function setTheme(theme: "system" | "dark" | "light") {
    haptic("light");
    settings.update.mutate({ theme });
  }

  return (
    <div className="px-4 pt-5 pb-6">
      <h1 className="text-text-primary text-cn-2xl font-semibold mb-4">{t("settings.title")}</h1>

      <SectionLabel>Внешний вид</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border p-3">
        <div className="flex gap-2">
          {(["system", "dark", "light"] as const).map((opt) => (
            <button
              key={opt}
              onClick={() => setTheme(opt)}
              className={`flex-1 py-2.5 rounded-xl text-cn-sm font-semibold border ${
                s.theme === opt ? "bg-accent text-white border-accent" : "bg-surface-elevated text-text-secondary border-border"
              }`}
            >
              {opt === "system" ? t("settings.themeSystem") : opt === "dark" ? t("settings.themeDark") : t("settings.themeLight")}
            </button>
          ))}
        </div>
      </div>

      <SectionLabel>{t("settings.language")}</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border">
        <RowStatic label={t("settings.language")} value="Русский" />
      </div>

      <SectionLabel>{t("settings.notifications")}</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border divide-y divide-border">
        <RowToggle label={t("settings.notifications")} checked={s.notifications_enabled} onChange={() => toggle("notifications_enabled")} />
        <RowToggle label={t("settings.haptics")} checked={s.haptic_feedback} onChange={() => toggle("haptic_feedback")} />
      </div>

      <SectionLabel>Приватность</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border p-4 text-text-secondary text-cn-sm leading-relaxed">
        CodeNexa хранит только данные, необходимые для работы приложения: профиль из Telegram, избранное, историю
        открытых модулей и настройки. Данные не передаются третьим лицам.
      </div>

      <SectionLabel>Аккаунт</SectionLabel>
      <div className="rounded-2xl bg-surface border border-border overflow-hidden">
        {!confirmingLogout ? (
          <button onClick={() => setConfirmingLogout(true)} className="w-full text-left px-4 py-3 text-cn-base font-medium text-error">
            Выйти
          </button>
        ) : (
          <div className="px-4 py-3">
            <p className="text-text-secondary text-cn-sm mb-2.5">
              Приложение закроется, при следующем запуске вы авторизуетесь автоматически через Telegram.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => { clearStoredToken(); closeMiniApp(); }}
                className="flex-1 py-2 rounded-lg bg-error/15 text-error text-cn-sm font-semibold"
              >
                Подтвердить
              </button>
              <button
                onClick={() => setConfirmingLogout(false)}
                className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-cn-sm font-semibold"
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

function RowStatic({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-text-primary text-cn-base">{label}</span>
      <span className="text-text-secondary text-[13px]">{value}</span>
    </div>
  );
}

function RowToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-text-primary text-cn-base">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={onChange}
        className={`w-11 h-6 rounded-full relative transition-colors ${checked ? "bg-accent" : "bg-border"}`}
      >
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${checked ? "translate-x-[22px]" : "translate-x-0.5"}`} />
      </button>
    </div>
  );
}
