import { useEffect, useState } from "react";
import t from "@/i18n";
import { initTelegram, isInsideTelegram } from "@/lib/telegram";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { ApiClientError } from "@/lib/apiClient";
import { clearStoredToken } from "@/lib/tokenStorage";

interface AuthGateProps {
  children: React.ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const [telegramReady, setTelegramReady] = useState(false);
  const user = useCurrentUser();

  useEffect(() => {
    initTelegram();
    setTelegramReady(true);
  }, []);

  if (!telegramReady) return <LoadingState />;

  if (!isInsideTelegram() && import.meta.env.PROD) {
    return <ErrorState message="Откройте это приложение через Telegram." />;
  }

  if (user.isLoading) return <LoadingState />;

  if (user.isError) {
    const err = user.error;
    console.error("Auth failed:", err);

    // A new database invalidates users/sessions created in the old database.
    // Drop the stale JWT so apiClient performs a fresh Telegram authentication.
    if (err instanceof ApiClientError && (err.status === 401 || err.status === 404)) {
      clearStoredToken();
      return (
        <ErrorState
          message="Сессия устарела. Повторно открываем авторизацию через Telegram…"
          onRetry={() => user.refetch()}
        />
      );
    }

    return <ErrorState message={t("errors.authFailed")} onRetry={() => user.refetch()} />;
  }

  return <>{children}</>;
}
