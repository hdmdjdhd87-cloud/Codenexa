import { haptic } from "@/lib/telegram";
import { useAiDocsTemplates } from "../hooks";
import type { AiDocsTemplate } from "@/services/aidocsService";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleListSkeleton } from "@/components/states/Skeleton";
import { CATEGORY_LABELS } from "../shared";

export function TemplatesView({ onSelect }: { onSelect: (t: AiDocsTemplate) => void }) {
  const templates = useAiDocsTemplates();

  return (
    <div>
      <h3 className="text-text-primary text-[14px] font-semibold mb-2.5">Выберите шаблон</h3>
      {templates.isLoading && <ModuleListSkeleton count={4} />}
      {templates.isError && <ErrorState message="Не удалось загрузить шаблоны." onRetry={() => templates.refetch()} />}
      {templates.data && templates.data.length === 0 && <EmptyState title="Шаблонов пока нет" />}
      {templates.data && templates.data.length > 0 && (
        <div className="flex flex-col gap-2">
          {templates.data.map((tpl) => (
            <button
              key={tpl.id}
              onClick={() => {
                haptic("light");
                onSelect(tpl);
              }}
              className="w-full text-left rounded-2xl bg-surface border border-border p-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-text-primary font-semibold text-[14px]">{tpl.name}</p>
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-accent/15 text-accent">
                  {CATEGORY_LABELS[tpl.category] ?? tpl.category}
                </span>
              </div>
              {tpl.description && <p className="text-text-secondary text-[12px] mt-1">{tpl.description}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
