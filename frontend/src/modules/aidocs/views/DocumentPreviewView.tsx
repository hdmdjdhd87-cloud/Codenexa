import { useRef, useState } from "react";
import { Star, Check, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { downloadAuthorizedFile } from "@/lib/apiClient";
import { haptic } from "@/lib/telegram";
import { aidocsService, type AiDocsAnalysis, type AiDocsVersionCompare } from "@/services/aidocsService";
import {
  useAiDocsDocument,
  useAiDocsVersions,
  useDeleteAiDoc,
  useToggleAiDocFavorite,
  useRenameAiDoc,
  useDuplicateAiDoc,
  useRestoreAiDocVersion,
  useCompareAiDocVersions,
  useAnalyzeAiDoc,
} from "../hooks";
import { formatDate } from "../shared";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";

export function DocumentPreviewView({
  documentId,
  onDeleted,
  onEditViaChat,
}: {
  documentId: string;
  onDeleted: () => void;
  onEditViaChat: () => void;
}) {
  const doc = useAiDocsDocument(documentId);
  const versions = useAiDocsVersions(documentId);
  const del = useDeleteAiDoc();
  const toggleFav = useToggleAiDocFavorite();
  const rename = useRenameAiDoc();
  const duplicate = useDuplicateAiDoc();
  const restoreVersion = useRestoreAiDocVersion();
  const compareVersions = useCompareAiDocVersions();
  const analyze = useAnalyzeAiDoc();
  const shareSubmittingRef = useRef(false);
  const duplicateSubmittingRef = useRef(false);
  const restoreSubmittingRef = useRef(false);
  const [downloading, setDownloading] = useState<"docx" | "pdf" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [shareOpen, setShareOpen] = useState(false);
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<string | null>(null);
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null);
  const [restoreNotice, setRestoreNotice] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelection, setCompareSelection] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<AiDocsVersionCompare | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AiDocsAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  async function handleRestore(versionId: string) {
    if (restoreSubmittingRef.current) return;
    restoreSubmittingRef.current = true;
    setRestoreError(null);
    haptic("light");
    try {
      // Двойная защита от повторного клика (п.7 промпта): синхронный ref
      // (эта проверка) закрывает гонку до перерисовки, disabled на кнопке —
      // видимую блокировку, а Idempotency-Key в aidocsService.restoreVersion —
      // защиту на уровне бэкенда, если оба клиентских барьера не сработали.
      const result = await restoreVersion.mutateAsync({ id: documentId, versionId });
      setRestoreNotice(`Восстановлена версия ${result.version.version_number}.`);
      setRestoringVersionId(null);
      setCompareResult(null);
      haptic("success");
    } catch (e) {
      setRestoreError(e instanceof Error ? e.message : "Не удалось восстановить версию.");
      haptic("error");
    } finally {
      restoreSubmittingRef.current = false;
    }
  }

  function toggleCompareSelection(versionId: string) {
    setCompareResult(null);
    setCompareError(null);
    setCompareSelection((prev) => {
      if (prev.includes(versionId)) return prev.filter((id) => id !== versionId);
      if (prev.length >= 2) return [prev[1], versionId];
      return [...prev, versionId];
    });
  }

  async function handleCompare() {
    if (compareSelection.length !== 2) return;
    setCompareError(null);
    haptic("light");
    try {
      // Порядок: старшая версия слева (from), младшая справа (to) — по
      // номеру версии, а не по порядку клика, чтобы diff читался как
      // "что изменилось с ... по ...", а не зависел от того, что выбрали первым.
      const versionA = versions.data?.find((v) => v.id === compareSelection[0]);
      const versionB = versions.data?.find((v) => v.id === compareSelection[1]);
      let fromId = compareSelection[0];
      let toId = compareSelection[1];
      if (versionA && versionB && versionA.version_number > versionB.version_number) {
        fromId = compareSelection[1];
        toId = compareSelection[0];
      }
      const result = await compareVersions.mutateAsync({ id: documentId, fromVersionId: fromId, toVersionId: toId });
      setCompareResult(result);
    } catch (e) {
      setCompareError(e instanceof Error ? e.message : "Не удалось сравнить версии.");
    }
  }

  async function handleAnalyze() {
    setAnalysisError(null);
    haptic("light");
    try {
      const result = await analyze.mutateAsync(documentId);
      setAnalysisResult(result);
      haptic(result.status === "error" ? "error" : result.status === "warning" ? "warning" : "success");
    } catch (e) {
      setAnalysisError(e instanceof Error ? e.message : "Не удалось проверить документ.");
      haptic("error");
    }
  }

  async function handleShare(expiresInDays: number | null) {
    if (shareSubmittingRef.current) return;
    shareSubmittingRef.current = true;
    setShareError(null);
    setShareLoading(true);
    haptic("light");
    try {
      const share = await aidocsService.createShare(documentId, expiresInDays);
      setShareLink(aidocsService.shareUrl(share.token));
    } catch (e) {
      setShareError(e instanceof Error ? e.message : "Не удалось создать ссылку.");
    } finally {
      setShareLoading(false);
      shareSubmittingRef.current = false;
    }
  }

  async function handleDuplicate() {
    if (duplicateSubmittingRef.current) return;
    duplicateSubmittingRef.current = true;
    haptic("light");
    try {
      const copy = await duplicate.mutateAsync(documentId);
      setDuplicateNotice(`Создана копия: «${copy.title}» — она в списке «Мои документы».`);
    } finally {
      duplicateSubmittingRef.current = false;
    }
  }

  async function handleExport(format: "docx" | "pdf") {
    setDownloadError(null);
    setDownloading(format);
    haptic("light");
    try {
      await downloadAuthorizedFile(
        aidocsService.exportUrl(documentId, format).replace(import.meta.env.VITE_API_BASE_URL, ""),
        `document.${format}`
      );
      haptic("success");
    } catch (e) {
      haptic("error");
      setDownloadError(e instanceof Error ? e.message : "Не удалось скачать файл.");
    } finally {
      setDownloading(null);
    }
  }

  if (doc.isLoading) return <LoadingState />;
  if (doc.isError || !doc.data) return <ErrorState message="Не удалось загрузить документ." onRetry={() => doc.refetch()} />;

  const d = doc.data;

  return (
    <div>
      <div className="flex items-start justify-between gap-3 mb-1.5">
        {!renaming ? (
          <h3
            onClick={() => {
              setRenameValue(d.title);
              setRenaming(true);
            }}
            className="text-text-primary text-[17px] font-semibold min-w-0 truncate cursor-pointer"
          >
            {d.title}
          </h3>
        ) : (
          <input
            autoFocus
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => {
              if (renameValue.trim() && renameValue !== d.title) rename.mutate({ id: documentId, title: renameValue.trim() });
              setRenaming(false);
            }}
            onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
            className="min-w-0 flex-1 bg-transparent border-b border-accent text-text-primary text-[17px] font-semibold outline-none"
          />
        )}
        <button
          onClick={() => toggleFav.mutate({ id: documentId, is_favorite: !d.is_favorite })}
          className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
            d.is_favorite ? "text-warning" : "text-text-secondary/50"
          }`}
        >
          <Star size={17} fill={d.is_favorite ? "currentColor" : "none"} aria-hidden="true" />
        </button>
      </div>
      <p className="text-text-secondary text-[11px] mb-4">Нажмите на название, чтобы переименовать</p>

      {/* "Лист документа" — предпросмотр как страница, не просто список текста */}
      <div className="rounded-2xl bg-white text-black p-5 shadow-inner" style={{ fontFamily: "Georgia, serif" }}>
        {(d.content_blocks ?? []).map((block, i) => {
          if (block.type === "spacer") return <div key={i} className="h-3" />;
          if (block.type === "heading_center")
            return (
              <p key={i} className="text-center font-bold text-[15px] my-2">
                {block.text}
              </p>
            );
          if (block.type === "heading")
            return (
              <p key={i} className="font-bold text-[13.5px] mt-3 mb-1">
                {block.text}
              </p>
            );
          if (block.type === "paragraph_right") return (
            <p key={i} className="text-right text-[12.5px]">{block.text}</p>
          );
          if (block.type === "signature_line")
            return (
              <p key={i} className="text-[12.5px] mt-4">
                {block.text} &nbsp;&nbsp; _______________
              </p>
            );
          return (
            <p key={i} className="text-[12.5px] leading-relaxed text-justify my-1.5">
              {block.text}
            </p>
          );
        })}
      </div>

      {downloadError && <p className="text-error text-[12.5px] mt-3">{downloadError}</p>}

      <div className="grid grid-cols-2 gap-2 mt-4">
        <button
          onClick={() => handleExport("docx")}
          disabled={downloading !== null}
          className="py-3 rounded-xl bg-surface border border-border text-text-primary text-[13px] font-semibold disabled:opacity-60"
        >
          {downloading === "docx" ? "Готовим…" : "Скачать DOCX"}
        </button>
        <button
          onClick={() => handleExport("pdf")}
          disabled={downloading !== null}
          className="py-3 rounded-xl bg-surface border border-border text-text-primary text-[13px] font-semibold disabled:opacity-60"
        >
          {downloading === "pdf" ? "Готовим…" : "Скачать PDF"}
        </button>
      </div>

      <div className="mt-2">
        <button
          onClick={onEditViaChat}
          className="w-full py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[12.5px] font-semibold mb-2"
        >
          Изменить через чат
        </button>
        <button
          onClick={handleAnalyze}
          disabled={analyze.isPending}
          className="w-full py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[12.5px] font-semibold disabled:opacity-60"
        >
          {analyze.isPending ? "Проверяем…" : "Анализировать документ"}
        </button>
        {analysisError && <p className="text-error text-[12px] mt-2">{analysisError}</p>}
        {analysisResult && <AnalysisResultCard result={analysisResult} onDismiss={() => setAnalysisResult(null)} />}
      </div>

      <div className="grid grid-cols-2 gap-2 mt-2">
        <button
          onClick={handleDuplicate}
          disabled={duplicate.isPending}
          className="py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[12.5px] font-semibold disabled:opacity-60"
        >
          {duplicate.isPending ? "Копируем…" : "Создать копию"}
        </button>
        <button
          onClick={() => setShareOpen((v) => !v)}
          className="py-2.5 rounded-xl bg-surface border border-border text-text-primary text-[12.5px] font-semibold"
        >
          Поделиться
        </button>
      </div>
      {duplicateNotice && <p className="text-success text-[12px] mt-2">{duplicateNotice}</p>}

      {shareOpen && (
        <div className="rounded-xl bg-surface border border-border p-3.5 mt-2">
          {!shareLink ? (
            <>
              <p className="text-text-secondary text-[12px] mb-2.5">
                Создаётся view-only ссылка — по ней документ можно только посмотреть, без авторизации.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleShare(7)}
                  disabled={shareLoading}
                  className="flex-1 py-2 rounded-lg bg-accent text-white text-[12.5px] font-semibold disabled:opacity-60"
                >
                  {shareLoading ? "Создаём…" : "На 7 дней"}
                </button>
                <button
                  onClick={() => handleShare(null)}
                  disabled={shareLoading}
                  className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold disabled:opacity-60"
                >
                  Бессрочно
                </button>
              </div>
              {shareError && <p className="text-error text-[12px] mt-2">{shareError}</p>}
            </>
          ) : (
            <>
              <p className="text-text-secondary text-[11.5px] mb-1.5">Ссылка готова:</p>
              <div className="rounded-lg bg-surface-elevated p-2.5 text-[11.5px] text-accent break-all">{shareLink}</div>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(shareLink);
                  haptic("success");
                }}
                className="w-full mt-2 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold"
              >
                Скопировать
              </button>
            </>
          )}
        </div>
      )}

      {versions.data && versions.data.length > 0 && (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-text-secondary text-[12px] font-semibold uppercase tracking-wide">История версий</p>
            {versions.data.length > 1 && (
              <button
                onClick={() => {
                  setCompareMode((v) => !v);
                  setCompareSelection([]);
                  setCompareResult(null);
                  setCompareError(null);
                }}
                className="text-accent text-[12px] font-semibold"
              >
                {compareMode ? "Отмена" : "Сравнить версии"}
              </button>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {versions.data.map((v, idx) => {
              const isLatest = idx === 0; // список отсортирован version_number desc
              const selected = compareSelection.includes(v.id);
              return (
                <div
                  key={v.id}
                  className={`rounded-xl px-3 py-2.5 border ${
                    compareMode && selected ? "border-accent bg-accent/10" : "border-border bg-surface"
                  }`}
                >
                  <div
                    className="flex items-center justify-between gap-2"
                    onClick={compareMode ? () => toggleCompareSelection(v.id) : undefined}
                  >
                    <div className="min-w-0">
                      <p className="text-text-primary text-[12.5px] font-medium truncate">
                        Версия {v.version_number} {isLatest && "· текущая"}
                        {v.note ? ` — ${v.note}` : ""}
                      </p>
                      <p className="text-text-secondary text-[11px] mt-0.5">{formatDate(v.created_at)}</p>
                    </div>
                    {compareMode ? (
                      <span
                        className={`shrink-0 w-5 h-5 rounded-full border flex items-center justify-center ${
                          selected ? "bg-accent border-accent text-white" : "border-border text-transparent"
                        }`}
                      >
                        <Check size={12} aria-hidden="true" />
                      </span>
                    ) : (
                      !isLatest &&
                      restoringVersionId !== v.id && (
                        <button
                          onClick={() => setRestoringVersionId(v.id)}
                          className="shrink-0 text-accent text-[12px] font-semibold"
                        >
                          Восстановить
                        </button>
                      )
                    )}
                  </div>

                  {!compareMode && restoringVersionId === v.id && (
                    <div className="mt-2.5 pt-2.5 border-t border-border/60">
                      <p className="text-text-secondary text-[11.5px] mb-2">
                        Текущее содержимое документа будет заменено версией {v.version_number}. Это создаст новую
                        версию в истории — старые версии не удаляются.
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleRestore(v.id)}
                          disabled={restoreVersion.isPending}
                          className="flex-1 py-2 rounded-lg bg-accent text-white text-[12px] font-semibold disabled:opacity-60"
                        >
                          {restoreVersion.isPending ? "Восстанавливаем…" : "Подтвердить"}
                        </button>
                        <button
                          onClick={() => setRestoringVersionId(null)}
                          disabled={restoreVersion.isPending}
                          className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12px] font-semibold disabled:opacity-60"
                        >
                          Отмена
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {restoreNotice && <p className="text-success text-[12px] mt-2">{restoreNotice}</p>}
          {restoreError && <p className="text-error text-[12px] mt-2">{restoreError}</p>}

          {compareMode && (
            <div className="mt-3">
              <button
                onClick={handleCompare}
                disabled={compareSelection.length !== 2 || compareVersions.isPending}
                className="w-full py-2.5 rounded-xl bg-accent text-white text-[12.5px] font-semibold disabled:opacity-60"
              >
                {compareVersions.isPending
                  ? "Сравниваем…"
                  : compareSelection.length !== 2
                    ? "Выберите 2 версии"
                    : "Сравнить"}
              </button>
              {compareError && <p className="text-error text-[12px] mt-2">{compareError}</p>}
              {compareResult && <VersionCompareResult result={compareResult} />}
            </div>
          )}
        </div>
      )}

      <div className="mt-6">
        {!confirmingDelete ? (
          <button onClick={() => setConfirmingDelete(true)} className="text-error text-[13px] font-semibold">
            Удалить документ
          </button>
        ) : (
          <div className="rounded-xl bg-surface border border-border p-3.5">
            <p className="text-text-secondary text-[12.5px] mb-2.5">Документ будет удалён безвозвратно.</p>
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  await del.mutateAsync(documentId);
                  onDeleted();
                }}
                className="flex-1 py-2 rounded-lg bg-error/15 text-error text-[12.5px] font-semibold"
              >
                Подтвердить
              </button>
              <button
                onClick={() => setConfirmingDelete(false)}
                className="flex-1 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary text-[12.5px] font-semibold"
              >
                Отмена
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================= ANALYSIS ============================= */

const ANALYSIS_STATUS_META: Record<string, { Icon: typeof CheckCircle2; label: string; color: string }> = {
  pass: { Icon: CheckCircle2, label: "Замечаний нет", color: "text-success" },
  warning: { Icon: AlertTriangle, label: "Есть на что обратить внимание", color: "text-warning" },
  error: { Icon: XCircle, label: "Требует исправлений", color: "text-error" },
};

const SEVERITY_LABELS: Record<string, string> = {
  error: "Ошибка",
  warning: "Предупреждение",
  info: "Информация",
};

function AnalysisResultCard({ result, onDismiss }: { result: AiDocsAnalysis; onDismiss: () => void }) {
  const meta = ANALYSIS_STATUS_META[result.status] ?? ANALYSIS_STATUS_META.warning;
  return (
    <div className="rounded-xl bg-surface border border-border p-3.5 mt-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <meta.Icon size={18} className={meta.color} aria-hidden="true" />
          <p className={`text-[13px] font-semibold ${meta.color}`}>{meta.label}</p>
        </div>
        <button onClick={onDismiss} className="text-text-secondary text-[12px] shrink-0">
          Скрыть
        </button>
      </div>

      {result.issues.length > 0 ? (
        <div className="flex flex-col gap-2 mt-3">
          {result.issues.map((issue, i) => (
            <div key={i} className="rounded-lg bg-surface-elevated border border-border p-2.5">
              <div className="flex items-center gap-1.5 mb-1">
                <span
                  className={`text-[10px] font-semibold uppercase tracking-wide ${
                    issue.severity === "error"
                      ? "text-error"
                      : issue.severity === "warning"
                        ? "text-warning"
                        : "text-text-secondary"
                  }`}
                >
                  {SEVERITY_LABELS[issue.severity] ?? issue.severity}
                </span>
                <span className="text-text-secondary text-[10px]">· {issue.category}</span>
              </div>
              <p className="text-text-primary text-[12.5px]">{issue.message}</p>
              {issue.suggestion && <p className="text-text-secondary text-[11.5px] mt-1">{issue.suggestion}</p>}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-text-secondary text-[12px] mt-2">Структурных проблем не найдено.</p>
      )}

      <p className="text-text-secondary text-[10.5px] mt-3">{result.disclaimer}</p>
    </div>
  );
}

/* ============================= VERSION COMPARE ============================= */

function VersionCompareResult({ result }: { result: AiDocsVersionCompare }) {
  const { summary, blocks } = result.diff;
  return (
    <div className="rounded-xl bg-surface border border-border p-3.5 mt-2.5">
      <p className="text-text-secondary text-[11.5px] mb-2">
        Версия {result.from.version_number} → Версия {result.to.version_number}
      </p>
      <div className="flex gap-3 mb-3 text-[11.5px]">
        <span className="text-success">+{summary.added}</span>
        <span className="text-error">−{summary.removed}</span>
        <span className="text-warning">~{summary.changed}</span>
        <span className="text-text-secondary">{summary.unchanged} без изменений</span>
      </div>

      <div className="flex flex-col gap-2">
        {blocks
          .filter((b) => b.op !== "unchanged")
          .map((b, i) => (
            <div
              key={i}
              className={`rounded-lg p-2.5 border text-[12px] ${
                b.op === "added"
                  ? "bg-success/10 border-success/30"
                  : b.op === "removed"
                    ? "bg-error/10 border-error/30"
                    : "bg-warning/10 border-warning/30"
              }`}
            >
              {b.op === "added" && <p className="text-text-primary">+ {b.new_text}</p>}
              {b.op === "removed" && <p className="text-text-primary line-through opacity-70">− {b.old_text}</p>}
              {b.op === "changed" && (
                <p className="text-text-primary leading-relaxed">
                  {b.word_diff.map((part, j) =>
                    part.op === "equal" ? (
                      <span key={j}>{part.text} </span>
                    ) : part.op === "delete" ? (
                      <span key={j} className="line-through opacity-60">
                        {part.text}{" "}
                      </span>
                    ) : (
                      <span key={j} className="text-success font-medium">
                        {part.text}{" "}
                      </span>
                    )
                  )}
                </p>
              )}
            </div>
          ))}
        {blocks.every((b) => b.op === "unchanged") && (
          <p className="text-text-secondary text-[12px]">Версии идентичны.</p>
        )}
      </div>
    </div>
  );
}
