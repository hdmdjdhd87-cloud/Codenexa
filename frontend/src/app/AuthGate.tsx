import { useEffect, useState } from "react";
import t from "@/i18n";
import { initTelegram, isInsideTelegram } from "@/lib/telegram";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { ApiClientError } from "@/lib/apiClient";

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
    // Пользователю — понятное сообщение (п.27 спецификации: не техническая
    // ошибка на экране). Технические детали — только в консоль разработчика.
    const err = user.error;
    if (err instanceof ApiClientError) {
      console.error(`Auth failed: [${err.code}] ${err.message} (status ${err.status})`);
    } else {
      console.error("Auth failed:", err);
    }
    return <ErrorState message={t("errors.authFailed")} onRetry={() => user.refetch()} />;
  }

  return <>{children}</>;
}

