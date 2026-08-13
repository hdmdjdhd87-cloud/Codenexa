import t from "@/i18n";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-6" role="alert">
      <div className="w-12 h-12 rounded-2xl bg-error/10 border border-error/30 mb-4" aria-hidden="true" />
      <p className="text-text-primary font-medium text-[15px] whitespace-pre-line">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-5 px-5 py-2.5 rounded-xl bg-surface-elevated border border-border text-[13px] font-semibold text-text-primary active:scale-95 transition-transform"
        >
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}
