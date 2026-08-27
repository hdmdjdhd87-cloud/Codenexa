import { NavLink } from "react-router-dom";
import { Home, LayoutGrid, Star, History as HistoryIcon, CircleUser } from "lucide-react";
import t from "@/i18n";

const ITEMS = [
  { to: "/", label: () => t("nav.home"), Icon: Home },
  { to: "/catalog", label: () => t("nav.catalog"), Icon: LayoutGrid },
  { to: "/favorites", label: () => t("nav.favorites"), Icon: Star },
  { to: "/history", label: () => t("nav.history"), Icon: HistoryIcon },
  { to: "/profile", label: () => t("nav.profile"), Icon: CircleUser },
];

export function BottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-cn-nav bg-surface/95 backdrop-blur border-t border-border pb-[env(safe-area-inset-bottom)]"
      aria-label={t("nav.home")}
    >
      <div className="flex items-stretch max-w-[560px] mx-auto">
        {ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-1 py-2.5 text-[10.5px] font-medium ${
                isActive ? "text-accent" : "text-text-secondary"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                {label()}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
