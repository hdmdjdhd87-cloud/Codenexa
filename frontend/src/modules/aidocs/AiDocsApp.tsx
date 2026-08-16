import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hideBackButton, showBackButton, haptic } from "@/lib/telegram";
import { downloadAuthorizedFile } from "@/lib/apiClient";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { aidocsService, type AiDocsTemplate } from "@/services/aidocsService";
import {
  useAiStatus,
  useAiDocsTemplates,
  useAiDocsDocuments,
  useAiDocsDocument,
  useAiDocsVersions,
  useCreateAiDoc,
  useDeleteAiDoc,
  useToggleAiDocFavorite,
  useRenameAiDoc,
  useDuplicateAiDoc,
} from "./hooks";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleListSkeleton } from "@/components/states/Skeleton";

type View = "list" | "templates" | "create" | "preview";

const CATEGORY_LABELS: Record<string, string> = {
  business: "Деловые",
  personal: "Личные",
  legal: "Юридические",
  universal: "Универсальные",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function AiDocsApp() {
  const navigate = useNavigate();
  const [view, setView] = useState<View>("list");
  const [selectedTemplate, setSelectedTemplate] = useState<AiDocsTemplate | null>(null);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);

  const status = useAiStatus();

  // Telegram BackButton: внутри модуля сначала возвращаемся на список,
  // и только с самого списка — обратно в каталог CodeNexa.
  useEffect(() => {
    const onBack = () => {
      if (view === "create") setView("templates");
      else if (view === "preview") setView("list");
      else if (view === "templates") setView("list");
      else navigate("/catalog");
    };
    showBackButton(onBack);
    return () => hideBackButton(onBack);
  }, [view, navigate]);

  return (
    <div className="px-4 pt-5 pb-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-text-primary text-[20px] font-semibold">AI Docs</h1>
        {status.data && !status.data.ai_available && (
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-warning/15 text-warning">
            AI недоступен
          </span>
        )}
      </div>

      {view === "list" && (
        <DocumentListView
          onCreateClick={() => setView("templates")}
          onOpen={(id) => {
            setActiveDocId(id);
            setView("preview");
          }}
        />
      )}
      {view === "templates" && (
        <TemplatesView
          onSelect={(tpl) => {
            setSelectedTemplate(tpl);
            setView("create");
          }}
        />
      )}
      {view === "create" && selectedTemplate && (
        <CreateDocumentView
          template={selectedTemplate}
          onCreated={(id) => {
            setActiveDocId(id);
            setView("preview");
          }}
        />
      )}
      {view === "preview" && activeDocId && (
        <DocumentPreviewView documentId={activeDocId} onDeleted={() => setView("list")} />
      )}
    </div>
  );
}

/* ============================= LIST ============================= */

function DocumentListView({ onCreateClick, onOpen }: { onCreateClick: () => void; onOpen: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 250);
  const documents = useAiDocsDocuments(debouncedQuery);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

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
        className="w-full py-3.5 rounded-2xl bg-accent text-white font-semibold text-[14px] mb-2.5"
      >
        + Создать документ
      </button>

      <label className="w-full flex items-center justify-center gap-2 py-2.5 rounded-2xl bg-surface border border-border text-text-primary text-[13px] font-semibold mb-4 cursor-pointer">
        {importing ? "Импортируем…" : "📄 Загрузить документ (DOCX/PDF)"}
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
        className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-[13.5px] text-text-primary placeholder:text-text-secondary outline-none focus:border-accent mb-4"
      />

      <h3 className="text-text-primary text-[14px] font-semibold mb-2.5">Мои документы</h3>

      {documents.isLoading && <ModuleListSkeleton count={3} />}
      {documents.isError && <ErrorState message="Не удалось загрузить документы." onRetry={() => documents.refetch()} />}
      {documents.data && documents.data.length === 0 && (
        <EmptyState
          title={query ? "Ничего не найдено" : "Здесь пока ничего нет"}
          description={query ? "Попробуйте другой запрос." : "Создайте первый документ по шаблону выше."}
        />
      )}
      {documents.data && documents.data.length > 0 && (
        <div className="flex flex-col gap-2">
          {documents.data.map((doc) => (
            <button
              key={doc.id}
              onClick={() => onOpen(doc.id)}
              className="w-full text-left rounded-2xl bg-surface border border-border p-4 flex items-center justify-between"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-text-primary font-semibold text-[14px] truncate">{doc.title}</p>
                  {doc.is_favorite && <span className="text-warning text-[12px]">★</span>}
                </div>
                <p className="text-text-secondary text-[12px] mt-0.5">
                  {CATEGORY_LABELS[doc.doc_type] ?? doc.doc_type} · {formatDate(doc.updated_at)}
                </p>
              </div>
              <span className="text-text-secondary/40 text-[16px] shrink-0">›</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================= TEMPLATES ============================= */

function TemplatesView({ onSelect }: { onSelect: (t: AiDocsTemplate) => void }) {
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

/* ============================= CREATE (FORM) ============================= */

function CreateDocumentView({ template, onCreated }: { template: AiDocsTemplate; onCreated: (id: string) => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const create = useCreateAiDoc();

  function setField(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handlePhotoUpload(file: File) {
    setOcrError(null);
    setOcrText(null);
    setOcrLoading(true);
    haptic("light");
    try {
      const result = await aidocsService.ocr(file);
      setOcrText(result.text || "");
      if (!result.text) {
        setOcrError("Текст на изображении не распознан. Попробуйте более чёткое фото.");
      }
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : "Не удалось распознать изображение.");
    } finally {
      setOcrLoading(false);
    }
  }

  async function handleSubmit() {
    setError(null);
    haptic("light");
    try {
      const doc = await create.mutateAsync({
        template_id: template.id,
        title: template.name,
        field_values: values,
      });
      haptic("success");
      onCreated(doc.id);
    } catch (e) {
      haptic("error");
      setError(e instanceof Error ? e.message : "Не удалось создать документ.");
    }
  }

  return (
    <div>
      <h3 className="text-text-primary text-[16px] font-semibold mb-1">{template.name}</h3>
      <p className="text-text-secondary text-[12.5px] mb-4">Заполните данные — документ соберётся автоматически.</p>

      {/* Загрузка фото/скана: настоящий OCR (Tesseract), без AI-понимания
          структуры — честно распознаёт текст, пользователь сам переносит
          нужное в поля ниже. */}
      <div className="rounded-xl bg-surface border border-border p-3.5 mb-4">
        <label className="flex items-center justify-center gap-2 py-2.5 rounded-lg border border-dashed border-border text-text-secondary text-[12.5px] font-medium cursor-pointer">
          📷 Загрузить фото/скан для распознавания текста
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handlePhotoUpload(file);
              e.target.value = "";
            }}
          />
        </label>
        {ocrLoading && <p className="text-text-secondary text-[12px] mt-2">Распознаём текст…</p>}
        {ocrError && <p className="text-error text-[12px] mt-2">{ocrError}</p>}
        {ocrText && (
          <div className="mt-2.5">
            <p className="text-text-secondary text-[11px] mb-1">
              Распознанный текст (перенесите нужное в поля вручную — автоматическое понимание структуры требует AI, пока недоступно):
            </p>
            <div className="rounded-lg bg-surface-elevated p-2.5 text-[12px] text-text-primary whitespace-pre-wrap max-h-32 overflow-y-auto">
              {ocrText}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {template.fields_schema.map((field) => (
          <div key={field.key}>
            <label className="block text-text-secondary text-[12px] font-medium mb-1.5">
              {field.label}
              {field.required && <span className="text-error"> *</span>}
            </label>
            {field.type === "textarea" ? (
              <textarea
                value={values[field.key] || ""}
                onChange={(e) => setField(field.key, e.target.value)}
                rows={4}
                className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-[13.5px] text-text-primary outline-none focus:border-accent resize-none"
              />
            ) : (
              <input
                type={field.type === "date" ? "date" : "text"}
                value={values[field.key] || ""}
                onChange={(e) => setField(field.key, e.target.value)}
                className="w-full rounded-xl bg-surface border border-border px-3.5 py-2.5 text-[13.5px] text-text-primary outline-none focus:border-accent"
              />
            )}
          </div>
        ))}
      </div>

      {error && <p className="text-error text-[12.5px] mt-3">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={create.isPending}
        className="w-full mt-5 py-3.5 rounded-2xl bg-accent text-white font-semibold text-[14px] disabled:opacity-60"
      >
        {create.isPending ? "Создаём…" : "Создать документ"}
      </button>
    </div>
  );
}

/* ============================= PREVIEW ============================= */

function DocumentPreviewView({ documentId, onDeleted }: { documentId: string; onDeleted: () => void }) {
  const doc = useAiDocsDocument(documentId);
  const versions = useAiDocsVersions(documentId);
  const del = useDeleteAiDoc();
  const toggleFav = useToggleAiDocFavorite();
  const rename = useRenameAiDoc();
  const duplicate = useDuplicateAiDoc();
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

  async function handleShare(expiresInDays: number | null) {
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
    }
  }

  async function handleDuplicate() {
    haptic("light");
    const copy = await duplicate.mutateAsync(documentId);
    setDuplicateNotice(`Создана копия: «${copy.title}» — она в списке «Мои документы».`);
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
          className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-[16px] ${
            d.is_favorite ? "text-warning" : "text-text-secondary/50"
          }`}
        >
          {d.is_favorite ? "★" : "☆"}
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
          <p className="text-text-secondary text-[12px] font-semibold uppercase tracking-wide mb-2">История версий</p>
          <div className="flex flex-col gap-1.5">
            {versions.data.map((v) => (
              <div key={v.id} className="flex items-center justify-between text-[12.5px] px-1">
                <span className="text-text-primary">Версия {v.version_number} — {v.note}</span>
                <span className="text-text-secondary">{formatDate(v.created_at)}</span>
              </div>
            ))}
          </div>
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
