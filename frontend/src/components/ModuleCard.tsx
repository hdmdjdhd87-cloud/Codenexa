import { Link } from "react-router-dom";
import t from "@/i18n";
import type { ModuleDefinition } from "@/types";
import { haptic } from "@/lib/telegram";
import { colorFromString } from "@/lib/colorFromString";

interface ModuleCardProps {
  module: ModuleDefinition;
  isFavorite?: boolean;
  onToggleFavorite?: (moduleId: string) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  files: "Файлы",
  telegram: "Telegram",
  content: "Контент",
  design: "Дизайн",
  docs: "Документы",
  analytics: "Аналитика",
  productivity: "Продуктивность",
  development: "Разработка",
};

function isImageUrl(icon: string | null): icon is string {
  return !!icon && (icon.startsWith("http://") || icon.startsWith("https://") || icon.startsWith("/"));
}

export function ModuleCard({ module, isFavorite, onToggleFavorite }: ModuleCardProps) {
  const isComingSoon = module.status === "maintenance";
  const color = colorFromString(module.category || module.module_key);
  const iconIsImage = isImageUrl(module.icon);

  const content = (
    <div className="group rounded-2xl bg-surface border border-border p-3.5 flex items-center gap-3.5 transition-all duration-150 active:scale-[0.98] active:bg-surface-elevated">
      {/* Иконка модуля: реальная картинка (module.icon как URL), если задана,
          иначе — фирменная градиентная плашка с инициалом, привязанная
          цветом к категории (одна и та же категория = один и тот же цвет). */}
      <div
        className="w-12 h-12 shrink-0 rounded-2xl overflow-hidden flex items-center justify-center relative"
        style={!iconIsImage ? { background: `linear-gradient(155deg, ${color.bg}33, ${color.bg}0D)` } : undefined}
      >
        {iconIsImage ? (
          <img src={module.icon!} alt="" className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <>
            <div
              className="absolute inset-0 opacity-40"
              style={{ background: `radial-gradient(circle at 30% 20%, ${color.bg}55, transparent 70%)` }}
              aria-hidden="true"
            />
            <span className="relative font-semibold text-[17px]" style={{ color: color.bg }}>
              {module.name.charAt(0).toUpperCase()}
            </span>
          </>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="text-text-primary font-semibold text-[14px] truncate">{module.name}</p>
          {isComingSoon && (
            <span className="text-[9.5px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-warning/15 text-warning shrink-0">
              {t("catalog.comingSoon")}
            </span>
          )}
        </div>
        {module.description && (
          <p className="text-text-secondary text-[12px] mt-0.5 line-clamp-1">{module.description}</p>
        )}
        {module.category && (
          <span
            className="inline-block mt-1.5 text-[10px] font-medium px-1.5 py-[1px] rounded-md"
            style={{ background: color.tint, color: color.bg }}
          >
            {CATEGORY_LABELS[module.category] ?? module.category}
          </span>
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
          className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-[15px] transition-colors ${
            isFavorite ? "text-warning" : "text-text-secondary/50"
          }`}
        >
          {isFavorite ? "★" : "☆"}
        </button>
      )}

      {!onToggleFavorite && !isComingSoon && (
        <span className="text-text-secondary/40 text-[16px] shrink-0" aria-hidden="true">
          ›
        </span>
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
