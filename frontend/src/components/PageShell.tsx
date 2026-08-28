import type { ReactNode } from "react";

/**
 * Общая обёртка страницы: px-4 pt-5 pb-6 + заголовок h1, опционально с
 * действием справа (например "Отметить всё прочитанным" в Notifications).
 *
 * Извлечено из 5 страниц, дублировавших идентичную разметку буквально
 * (CatalogPage, FavoritesPage, HistoryPage, SettingsPage,
 * NotificationsPage) — п.6 UI/UX-спецификации: "Сделать shell,
 * одинаково качественный для всех разделов" + п.22: "Shared primitives...
 * не создавать отдельные несвязанные кнопки/styles для каждого продукта".
 *
 * HomePage НЕ использует этот компонент — там отдельный, более богатый
 * header (аватар/приветствие/колокольчик), это осознанное решение
 * дизайна Home, не пропущенное место для унификации.
 *
 * Безопасность рендера: страницы без action получают
 * `<div className="flex items-center justify-between mb-4">` с ЕДИНСТВЕННЫМ
 * ребёнком (h1) — при justify-between с одним элементом распределять
 * не с чем, элемент остаётся у начала строки, визуально идентично
 * прежнему одиночному `<h1 className="... mb-4">`.
 */
export function PageShell({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="px-4 pt-5 pb-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-text-primary text-cn-2xl font-semibold">{title}</h1>
        {action}
      </div>
      {children}
    </div>
  );
}
