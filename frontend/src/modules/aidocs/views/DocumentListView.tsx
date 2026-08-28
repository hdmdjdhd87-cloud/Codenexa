import { useState } from "react";
import { FileText, ChevronRight, Star } from "lucide-react";
import { haptic } from "@/lib/telegram";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { aidocsService } from "@/services/aidocsService";
import { useAiDocsDocuments } from "../hooks";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleListSkeleton } from "@/components/states/Skeleton";
import { CATEGORY_LABELS, formatDate } from "../shared";

function filteredDocuments<T extends { is_favorite: boolean; updated_at: string }>(
  docs: T[],
  filter: "all" | "favorites" | "recent"
): T[] {
  if (filter === "favorites") return docs.filter((d) => d.is_favorite);
  if (filter === "recent") {
    const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return docs.filter((d) => new Date(d.updated_at).getTime() >= weekAgo);
  }
  return docs;
}

export function DocumentListView({
  onCreateClick,
  onOpen,
}: {
  onCreateClick: () => void;
  onOpen: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 250);
  const documents = useAiDocsDocuments(debouncedQuery);
  const allDocs = documents.data?.pages.flat() ?? [];
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "favorites" | "recent">("all");

  async function handleImport(file: File) {
    setImportError(null);
    setImporting(true);
    haptic("light");
    try {
      const doc = await aidocsService.importDocument(file);
      haptic("success");
      onOpen(doc.id);
    } catch (e) {
      haptic("error");
      setImportError(e instanceof Error ? e.message : "Не удалось импортировать документ.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <button
        onClick={() => {
          haptic("light");
          onCreateClick();
        }}
        className="w-full py-3.5 rounded-2xl bg-accent text-white font-semibold text-cn-md mb-2.5"
      >
        + Создать документ
      </button>

      <label className="w-full flex items-center justify-center gap-2 py-2.5 rounded-2xl bg-surface border border-border text-text-primary text-[13px] font-semibold mb-4 cursor-pointer">
        {importing ? (
          "Импортируем…"
        ) : (
          <>
            <FileText size={16} aria-hidden="true" /> Загрузить документ (DOCX/PDF)
          </>
        )}
        <input
          type="file"
          accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          disabled={importing}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleImport(file);
            e.target.value = "";
          }}
        />
      </label>
      {importError && <p className="text-error text-[12px] -mt-2 mb-3">{importError}</p>}

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск по названию или тексту"
        className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-cn-base text-text-primary placeholder:text-text-secondary outline-none focus:border-accent mb-4"
      />

      <h3 className="text-text-primary text-cn-md font-semibold mb-2.5">Мои документы</h3>

      <div className="flex gap-1.5 mb-3">
        {(["all", "recent", "favorites"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-semibold ${
              filter === f ? "bg-accent text-white" : "bg-surface border border-border text-text-secondary"
            }`}
          >
            {f === "all" ? "Все" : f === "recent" ? "Недавние" : "Избранные"}
          </button>
        ))}
      </div>

      {documents.isLoading && <ModuleListSkeleton count={3} />}
      {documents.isError && <ErrorState message="Не удалось загрузить документы." onRetry={() => documents.refetch()} />}
      {documents.data && filteredDocuments(allDocs, filter).length === 0 && (
        <EmptyState
          title={query ? "Ничего не найдено" : "Здесь пока ничего нет"}
          description={query ? "Попробуйте другой запрос." : "Создайте первый документ по шаблону выше."}
        />
      )}
      {documents.data && filteredDocuments(allDocs, filter).length > 0 && (
        <div className="flex flex-col gap-2">
          {filteredDocuments(allDocs, filter).map((doc) => (
            <button
              key={doc.id}
              onClick={() => onOpen(doc.id)}
              className="w-full text-left rounded-2xl bg-surface border border-border p-4 flex items-center justify-between"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-text-primary font-semibold text-cn-md truncate">{doc.title}</p>
                  {doc.is_favorite && <Star size={13} className="text-warning" fill="currentColor" aria-hidden="true" />}
                </div>
                <p className="text-text-secondary text-[12px] mt-0.5">
                  {CATEGORY_LABELS[doc.doc_type] ?? doc.doc_type} · {formatDate(doc.updated_at)}
                </p>
              </div>
              <span className="text-text-secondary/40 shrink-0"><ChevronRight size={18} aria-hidden="true" /></span>
            </button>
          ))}
          {documents.hasNextPage && (
            <button
              onClick={() => documents.fetchNextPage()}
              disabled={documents.isFetchingNextPage}
              className="w-full py-2.5 rounded-xl bg-surface border border-border text-text-secondary text-cn-sm font-semibold disabled:opacity-60"
            >
              {documents.isFetchingNextPage ? "Загружаем…" : "Показать ещё"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
