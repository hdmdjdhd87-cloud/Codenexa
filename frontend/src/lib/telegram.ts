/* eslint-disable @typescript-eslint/no-explicit-any */

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: Record<string, unknown>;
  ready: () => void;
  expand: () => void;
  close: () => void;
  colorScheme: "light" | "dark";
  themeParams: Record<string, string>;
  viewportHeight: number;
  viewportStableHeight: number;
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    setText: (text: string) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
    selectionChanged: () => void;
  };
}

function getTelegramWebApp(): TelegramWebApp | null {
  const w = window as any;
  return w.Telegram && w.Telegram.WebApp ? (w.Telegram.WebApp as TelegramWebApp) : null;
}

/** true, если приложение реально открыто внутри Telegram WebView, а не в обычном браузере */
export function isInsideTelegram(): boolean {
  const app = getTelegramWebApp();
  return Boolean(app && app.initData);
}

export function initTelegram(): void {
  const app = getTelegramWebApp();
  if (!app) return;
  app.ready();
  app.expand();
}

export function getInitData(): string {
  const app = getTelegramWebApp();
  return app?.initData ?? "";
}

export function getColorScheme(): "light" | "dark" {
  const app = getTelegramWebApp();
  return app?.colorScheme ?? "dark";
}

export function showBackButton(onClick: () => void): void {
  const app = getTelegramWebApp();
  if (!app) return;
  app.BackButton.onClick(onClick);
  app.BackButton.show();
}

export function hideBackButton(onClick?: () => void): void {
  const app = getTelegramWebApp();
  if (!app) return;
  if (onClick) app.BackButton.offClick(onClick);
  app.BackButton.hide();
}

/** Умеренный haptic feedback — не вызывать на каждый клик (п.41 спецификации) */
export function haptic(kind: "success" | "error" | "warning" | "light" = "light"): void {
  const app = getTelegramWebApp();
  if (!app) return;
  try {
    if (kind === "success" || kind === "error" || kind === "warning") {
      app.HapticFeedback.notificationOccurred(kind);
    } else {
      app.HapticFeedback.impactOccurred("light");
    }
  } catch {
    // Haptic API недоступен в этой версии клиента Telegram — молча игнорируем.
  }
}

export function closeMiniApp(): void {
  const app = getTelegramWebApp();
  app?.close();
}
