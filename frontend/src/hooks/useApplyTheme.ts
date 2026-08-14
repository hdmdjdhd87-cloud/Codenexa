import { useEffect } from "react";
import { getColorScheme } from "@/lib/telegram";
import type { UserSettings } from "@/types";

/**
 * Реально применяет выбранную тему к <html data-theme="...">, а не
 * только хранит значение в БД. "Системная" — берёт colorScheme из
 * Telegram WebApp (не ломает native Telegram theme, п.25 спецификации
 * предыдущего промпта), с fallback на prefers-color-scheme в обычном браузере.
 */
export function useApplyTheme(theme: UserSettings["theme"] | undefined) {
  useEffect(() => {
    const resolved =
      theme === "dark" || theme === "light"
        ? theme
        : getColorScheme() ?? (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark");

    document.documentElement.setAttribute("data-theme", resolved);
  }, [theme]);
}
