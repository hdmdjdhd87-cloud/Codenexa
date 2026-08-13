import { NavLink } from "react-router-dom";
import t from "@/i18n";

const ITEMS = [
  { to: "/", label: () => t("nav.home"), icon: "●" },
  { to: "/catalog", label: () => t("nav.catalog"), icon: "▦" },
  { to: "/favorites", label: () => t("nav.favorites"), icon: "★" },
  { to: "/history", label: () => t("nav.history"), icon: "↺" },
  { to: "/profile", label: () => t("nav.profile"), icon: "◐" },
];

export function BottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 bg-surface/95 backdrop-blur border-t border-border pb-[env(safe-area-inset-bottom)]"
      aria-label={t("nav.home")}
    >
      <div className="flex items-stretch max-w-[560px] mx-auto">
        {ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-1 py-2.5 text-[10.5px] font-medium ${
                isActive ? "text-accent" : "text-text-secondary"
              }`
            }
          >
            <span className="text-[16px] leading-none" aria-hidden="true">{item.icon}</span>
            {item.label()}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
