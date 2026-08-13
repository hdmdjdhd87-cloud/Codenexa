import t from "@/i18n";

export function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-text-secondary" role="status" aria-live="polite">
      <div
        className="h-7 w-7 rounded-full border-2 border-border border-t-accent animate-spin mb-3"
        aria-hidden="true"
      />
      <span className="text-sm">{t("common.loading")}</span>
    </div>
  );
}
