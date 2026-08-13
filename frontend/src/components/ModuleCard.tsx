import { Link } from "react-router-dom";
import t from "@/i18n";
import type { ModuleDefinition } from "@/types";
import { haptic } from "@/lib/telegram";

interface ModuleCardProps {
  module: ModuleDefinition;
  isFavorite?: boolean;
  onToggleFavorite?: (moduleId: string) => void;
}

export function ModuleCard({ module, isFavorite, onToggleFavorite }: ModuleCardProps) {
  const isComingSoon = module.status === "maintenance";
  const content = (
    <div className="rounded-2xl bg-surface border border-border p-4 flex items-start gap-3 active:scale-[0.98] transition-transform">
      <div className="w-11 h-11 shrink-0 rounded-xl bg-surface-elevated border border-border flex items-center justify-center text-accent font-semibold text-[15px]">
        {module.name.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-text-primary font-semibold text-[14px] truncate">{module.name}</p>
          {isComingSoon && (
            <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-warning/15 text-warning shrink-0">
              {t("catalog.comingSoon")}
            </span>
          )}
        </div>
        {module.description && (
          <p className="text-text-secondary text-[12.5px] mt-0.5 line-clamp-2">{module.description}</p>
        )}
      </div>
      {onToggleFavorite && (
        <button
          aria-label={isFavorite ? t("module.removeFavorite") : t("module.addFavorite")}
          onClick={(e) => {
            e.preventDefault();
            haptic("light");
            onToggleFavorite(module.id);
          }}
          className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center border ${
            isFavorite ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface-elevated border-border text-text-secondary"
          }`}
        >
          ★
        </button>
      )}
    </div>
  );

  if (isComingSoon) {
    return <div aria-disabled="true">{content}</div>;
  }

  return (
    <Link to={`/apps/${module.module_key}`} aria-label={module.name}>
      {content}
    </Link>
  );
}
