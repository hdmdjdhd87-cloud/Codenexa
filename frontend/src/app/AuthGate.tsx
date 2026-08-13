import { useEffect, useState } from "react";
import t from "@/i18n";
import { initTelegram, isInsideTelegram } from "@/lib/telegram";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";

interface AuthGateProps {
  children: React.ReactNode;
}

/**
 * Гарантирует, что дальше рендерится только авторизованное состояние.
 * useCurrentUser() сам триггерит POST /api/v1/auth/telegram через
 * apiClient (см. ensureToken), если валидного токена ещё нет — сюда
 * не нужно дублировать логику авторизации.
 */
export function AuthGate({ children }: AuthGateProps) {
  const [telegramReady, setTelegramReady] = useState(false);
  const user = useCurrentUser();

  useEffect(() => {
    initTelegram();
    setTelegramReady(true);
  }, []);

  if (!telegramReady) return <LoadingState />;

  if (!isInsideTelegram() && import.meta.env.PROD) {
    return (
      <ErrorState message="Откройте это приложение через Telegram." />
    );
  }

  if (user.isLoading) return <LoadingState />;
  if (user.isError) {
    return <ErrorState message={t("errors.authFailed")} onRetry={() => user.refetch()} />;
  }

  return <>{children}</>;
}
