import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { hideBackButton, showBackButton, haptic } from "@/lib/telegram";
import { downloadAuthorizedFile } from "@/lib/apiClient";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { aidocsService, type AiDocsTemplate, type AiDocsAnalysis, type AiDocsVersionCompare, type AiDocsConversation } from "@/services/aidocsService";
import {
  useAiDocsTemplates,
  useAiDocsDocuments,
  useAiDocsDocument,
  useAiDocsVersions,
  useAiDocsActiveConversation,
  useCreateAiDoc,
  useDeleteAiDoc,
  useToggleAiDocFavorite,
  useRenameAiDoc,
  useDuplicateAiDoc,
  useRestoreAiDocVersion,
  useCompareAiDocVersions,
  useAnalyzeAiDoc,
} from "./hooks";
import { LoadingState } from "@/components/states/LoadingState";
import { ErrorState } from "@/components/states/ErrorState";
import { EmptyState } from "@/components/states/EmptyState";
import { ModuleListSkeleton } from "@/components/states/Skeleton";

type View = "home" | "list" | "templates" | "create" | "preview" | "chat" | "edit_chat";

const CATEGORY_LABELS: Record<string, string> = {
  business: "Деловые",
  personal: "Личные",
  legal: "Юридические",
  universal: "Универсальные",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

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

export function AiDocsApp() {
  const navigate = useNavigate();
  const [view, setView] = useState<View>("home");
  const [selectedTemplate, setSelectedTemplate] = useState<AiDocsTemplate | null>(null);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [chatInitialMessage, setChatInitialMessage] = useState<string | undefined>(undefined);
  const [resumeConversation, setResumeConversation] = useState<AiDocsConversation | null>(null);

  // Telegram BackButton: внутри модуля сначала возвращаемся на предыдущий
  // экран, и только с самой Главной AI Docs — обратно в каталог CodeNexa.
  useEffect(() => {
    const onBack = () => {
      if (view === "create") setView("templates");
      else if (view === "preview") setView("list");
      else if (view === "edit_chat") setView("preview");
      else if (view === "templates") setView("home");
      else if (view === "list") setView("home");
      else if (view === "chat") setView("home");
      else navigate("/catalog");
    };
    showBackButton(onBack);
    return () => hideBackButton(onBack);
  }, [view, navigate]);

  return (
    <div className="px-4 pt-5 pb-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-text-primary text-[20px] font-semibold">AI Docs</h1>
      </div>

      {view === "home" && (
        <AiDocsHomeView
          onOpenList={() => setView("list")}
          onOpenTemplates={() => setView("templates")}
          onOpenChat={(msg) => {
            setChatInitialMessage(msg);
            setResumeConversation(null);
            setView("chat");
          }}
          onResumeChat={(conv) => {
            setChatInitialMessage(undefined);
            setResumeConversation(conv);
            setView("chat");
          }}
          onOpen={(id) => {
            setActiveDocId(id);
            setView("preview");
          }}
        />
      )}
      {view === "chat" && (
        <ChatView
          initialMessage={chatInitialMessage}
          resumeConversation={resumeConversation}
          onDocumentCreated={(id) => {
            setActiveDocId(id);
            setView("preview");
          }}
        />
      )}
      {view === "edit_chat" && activeDocId && (
        <ChatView
          documentId={activeDocId}
          initialGreeting='Что нужно изменить в документе? Например: «замени сумму 150000 на 200000», «добавь пункт: Гарантия 12 месяцев», «измени срок на 6 месяцев».'
          onDocumentCreated={() => {}}
          onDocumentEdited={() => setView("preview")}
        />
      )}
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
        <DocumentPreviewView
          documentId={activeDocId}
          onDeleted={() => setView("list")}
          onEditViaChat={() => setView("edit_chat")}
        />
      )}
    </div>
  );
}

/* ============================= HOME ============================= */

function AiDocsHomeView({
  onOpenList,
  onOpenTemplates,
  onOpenChat,
  onResumeChat,
  onOpen,
}: {
  onOpenList: () => void;
  onOpenTemplates: () => void;
  onOpenChat: (initialMessage?: string) => void;
  onResumeChat: (conversation: AiDocsConversation) => void;
  onOpen: (id: string) => void;
}) {
  const documents = useAiDocsDocuments();
  const activeConversation = useAiDocsActiveConversation();
  const [quickInput, setQuickInput] = useState("");
  const [draftDismissed, setDraftDismissed] = useState(false);

  const total = documents.data?.length ?? 0;
  const favoritesCount = (documents.data ?? []).filter((d) => d.is_favorite).length;
  const lastDoc = (documents.data ?? [])[0]; // список уже отсортирован backend'ом по updated_at desc

  // Незавершённый диалог создания документа (п.6 промпта): backend уже
  // хранит состояние (nexa_docs_conversations), но раньше фронтенд его
  // никак не проверял при открытии AI Docs — черновик молча пропадал
  // из виду при закрытии Mini App. status "idle" без сообщений — это
  // просто пустая ещё не начатая беседа, не черновик, банер не нужен.
  const draft = activeConversation.data;
  const hasDraft =
    !!draft &&
    !draftDismissed &&
    (draft.status === "collecting" || draft.status === "ready_to_create") &&
    (draft.messages?.length ?? 0) > 0;

  return (
    <div>
      {hasDraft && draft && (
        <div className="rounded-2xl bg-accent/10 border border-accent/30 p-3.5 mb-4">
          <p className="text-text-primary text-[13px] font-semibold mb-1">Продолжить создание документа?</p>
          <p className="text-text-secondary text-[12px] mb-2.5 line-clamp-2">
            {draft.messages[draft.messages.length - 1]?.text || "У вас есть незавершённый диалог."}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onResumeChat(draft)}
              className="flex-1 py-2 rounded-lg bg-accent text-white text-[12.5px] font-semibold"
            >
              Продолжить
            </button>
            <button
              onClick={() => setDraftDismissed(true)}
              className="flex-1 py-2 rounded-lg bg-surface border border-border text-text-primary text-[12.5px] font-semibold"
            >
              Не сейчас
            </button>
          </div>
        </div>
      )}

      <p className="text-text-secondary text-[13px] mb-4">
        Создавайте и оформляйте документы — опишите задачу своими словами.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (quickInput.trim()) onOpenChat(quickInput.trim());
        }}
        className="rounded-2xl bg-surface border border-border p-3.5 mb-5"
      >
        <textarea
          value={quickInput}
          onChange={(e) => setQuickInput(e.target.value)}
          placeholder="Что нужно сделать с документом?"
          rows={2}
          className="w-full bg-transparent text-text-primary text-[13.5px] placeholder:text-text-secondary outline-none resize-none"
        />
        <div className="flex justify-end mt-1">
          <button
            type="submit"
            onClick={() => haptic("light")}
            className="px-4 py-2 rounded-xl bg-accent text-white text-[12.5px] font-semibold"
          >
            Отправить →
          </button>
        </div>
      </form>

      <div className="grid grid-cols-2 gap-2 mb-5">
        <QuickAction label="Создать по шаблону" onClick={onOpenTemplates} />
        <QuickAction label="Создать по фото" onClick={onOpenTemplates} />
        <QuickAction label="Мои документы" onClick={onOpenList} />
        <QuickAction label="Написать AI Docs" onClick={() => onOpenChat()} />
      </div>

      <div className="grid grid-cols-3 gap-2 mb-5">
        <StatCard label="Документов" value={total} />
        <StatCard label="Избранных" value={favoritesCount} />
        <StatCard label="Шаблонов" value={4} />
      </div>

      {lastDoc && (
        <div className="mb-5">
          <p className="text-text-secondary text-[12px] font-semibold uppercase tracking-wide mb-2">
            Последний документ
          </p>
          <button
            onClick={() => onOpen(lastDoc.id)}
            className="w-full text-left rounded-2xl bg-surface border border-border p-4 flex items-center justify-between"
          >
            <div className="min-w-0">
              <p className="text-text-primary font-semibold text-[14px] truncate">{lastDoc.title}</p>
              <p className="text-text-secondary text-[12px] mt-0.5">{formatDate(lastDoc.updated_at)}</p>
            </div>
            <span className="text-text-secondary/40 text-[16px] shrink-0">›</span>
          </button>
        </div>
      )}

      <button
        onClick={onOpenList}
        className="w-full py-3 rounded-2xl bg-surface border border-border text-text-primary text-[13.5px] font-semibold"
      >
        Все документы {total > 0 ? `(${total})` : ""}
      </button>
    </div>
  );
}

function QuickAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={() => {
        haptic("light");
        onClick();
      }}
      className="rounded-xl bg-surface border border-border py-3 px-3 text-left text-[12.5px] font-semibold text-text-primary"
    >
      {label}
    </button>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-surface border border-border p-3 text-center">
      <p className="text-text-primary text-[20px] font-semibold" style={{ fontFamily: "inherit" }}>
        {value}
      </p>
      <p className="text-text-secondary text-[10.5px] mt-0.5">{label}</p>
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
      {documents.data && filteredDocuments(documents.data, filter).length === 0 && (
        <EmptyState
          title={query ? "Ничего не найдено" : "Здесь пока ничего нет"}
          description={query ? "Попробуйте другой запрос." : "Создайте первый документ по шаблону выше."}
        />
      )}
      {documents.data && filteredDocuments(documents.data, filter).length > 0 && (
        <div className="flex flex-col gap-2">
          {filteredDocuments(documents.data, filter).map((doc) => (
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

/* ============================= CHAT ============================= */

interface ChatMessage {
  role: "user" | "agent";
  text: string;
}

function ChatView({
  initialMessage,
  initialGreeting,
  documentId,
  resumeConversation,
  onDocumentCreated,
  onDocumentEdited,
}: {
  initialMessage?: string;
  initialGreeting?: string;
  documentId?: string;
  resumeConversation?: AiDocsConversation | null;
  onDocumentCreated: (id: string) => void;
  onDocumentEdited?: (id: string) => void;
}) {
  const qc = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    resumeConversation && resumeConversation.messages.length > 0
      ? resumeConversation.messages.map((m) => ({ role: m.role, text: m.text }))
      : [
          {
            role: "agent",
            text: initialGreeting ?? "Опишите, какой документ нужен — я помогу собрать данные и создать его.",
          },
        ]
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>(resumeConversation?.id);
  const [quickActions, setQuickActions] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentInitial = useRef(false);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setError(null);
    setSending(true);
    setMessages((m) => [...m, { role: "user", text: trimmed }]);
    setInput("");
    haptic("light");
    try {
      const reply = await aidocsService.chat(trimmed, conversationId, documentId);
      setConversationId(reply.conversation_id);
      setMessages((m) => [...m, { role: "agent", text: reply.reply }]);
      setQuickActions(reply.quick_actions || []);
      if (reply.document) {
        haptic("success");
        onDocumentCreated(reply.document.id);
      }
      if (reply.edited_document) {
        haptic("success");
        // Документ изменён через чат (п.1 промпта) — обновляем превью/
        // историю версий, чтобы не показывать устаревший content_blocks.
        // Экран НЕ переключаем автоматически — пользователь может захотеть
        // внести ещё правки подряд, возврат к документу — по кнопке "Готово".
        qc.invalidateQueries({ queryKey: ["aidocs", "document", reply.edited_document.id] });
        qc.invalidateQueries({ queryKey: ["aidocs", "versions", reply.edited_document.id] });
        qc.invalidateQueries({ queryKey: ["aidocs", "documents"] });
      }
    } catch (e) {
      haptic("error");
      setError(e instanceof Error ? e.message : "Не удалось отправить сообщение.");
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (initialMessage && !sentInitial.current) {
      sentInitial.current = true;
      send(initialMessage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage]);

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 140px)" }}>
      {documentId && onDocumentEdited && (
        <div className="flex justify-end mb-2">
          <button onClick={() => onDocumentEdited(documentId)} className="text-accent text-[12.5px] font-semibold">
            Готово, вернуться к документу
          </button>
        </div>
      )}
      <div ref={scrollRef} className="flex-1 overflow-y-auto flex flex-col gap-2.5 pb-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed whitespace-pre-line ${
              m.role === "user" ? "self-end bg-accent text-white" : "self-start bg-surface border border-border text-text-primary"
            }`}
          >
            {m.text}
          </div>
        ))}
        {sending && (
          <div className="self-start bg-surface border border-border rounded-2xl px-3.5 py-2.5 text-[13px] text-text-secondary">
            Печатает…
          </div>
        )}
      </div>

      {error && <p className="text-error text-[12px] mb-2">{error}</p>}

      {quickActions.length > 0 && (
        <div className="flex gap-1.5 flex-wrap mb-2">
          {quickActions.map((qa) => (
            <button
              key={qa}
              disabled={sending}
              onClick={() => send(qa === "create" ? "да" : qa === "edit" ? "нет, изменить" : qa)}
              className="px-3 py-1.5 rounded-full bg-surface border border-border text-text-primary text-[12px] font-semibold disabled:opacity-50"
            >
              {qa === "create" ? "Создать" : qa === "edit" ? "Изменить" : qa}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-end gap-2 pt-2 border-t border-border"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          rows={1}
          placeholder="Напишите сообщение…"
          className="flex-1 rounded-xl bg-surface border border-border px-3.5 py-2.5 text-[13.5px] text-text-primary placeholder:text-text-secondary outline-none resize-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="shrink-0 w-10 h-10 rounded-xl bg-accent text-white font-semibold disabled:opacity-50"
        >
          →
        </button>
      </form>
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
  const [suggestedFields, setSuggestedFields] = useState<Record<string, string>>({});
  const create = useCreateAiDoc();

  function setField(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handlePhotoUpload(file: File) {
    setOcrError(null);
    setOcrText(null);
    setSuggestedFields({});
    setOcrLoading(true);
    haptic("light");
    try {
      const result = await aidocsService.ocr(file, template.id);
      setOcrText(result.text || "");
      setSuggestedFields(result.suggested_fields || {});
      if (!result.text) {
        setOcrError("Текст на изображении не распознан. Попробуйте более чёткое фото.");
      }
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : "Не удалось распознать изображение.");
    } finally {
      setOcrLoading(false);
    }
  }

  function applyAllSuggestions() {
    setValues((v) => ({ ...v, ...suggestedFields }));
    haptic("success");
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
              Распознанный текст (автоматическое понимание структуры целиком требует AI, пока недоступно — но
              сумму/срок/дату/телефон/email ниже уже удалось сопоставить с полями):
            </p>
            <div className="rounded-lg bg-surface-elevated p-2.5 text-[12px] text-text-primary whitespace-pre-wrap max-h-32 overflow-y-auto">
              {ocrText}
            </div>
            {Object.keys(suggestedFields).length > 0 && (
              <div className="mt-2.5 rounded-lg bg-accent/10 border border-accent/30 p-2.5 flex items-center justify-between gap-2">
                <p className="text-text-primary text-[12px]">
                  Найдено полей для автозаполнения: {Object.keys(suggestedFields).length}
                </p>
                <button onClick={applyAllSuggestions} className="shrink-0 text-accent text-[12px] font-semibold">
                  Заполнить всё
                </button>
              </div>
            )}
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
            {suggestedFields[field.key] && suggestedFields[field.key] !== values[field.key] && (
              <button
                onClick={() => setField(field.key, suggestedFields[field.key])}
                className="mt-1.5 text-[11.5px] text-accent font-medium"
              >
                Использовать из фото: «{suggestedFields[field.key]}»
              </button>
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

function DocumentPreviewView({
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
    setRestoreError(null);
    haptic("light");
    try {
      // Идемпотентность: пока запрос летит, restoreVersion.isPending уже
      // блокирует повторный клик на кнопке (см. disabled ниже) — двойной
      // клик не породит два новых восстановления подряд.
      const result = await restoreVersion.mutateAsync({ id: documentId, versionId });
      setRestoreNotice(`Восстановлена версия ${result.version.version_number}.`);
      setRestoringVersionId(null);
      setCompareResult(null);
      haptic("success");
    } catch (e) {
      setRestoreError(e instanceof Error ? e.message : "Не удалось восстановить версию.");
      haptic("error");
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
                        className={`shrink-0 w-5 h-5 rounded-full border flex items-center justify-center text-[10px] ${
                          selected ? "bg-accent border-accent text-white" : "border-border text-transparent"
                        }`}
                      >
                        ✓
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

const ANALYSIS_STATUS_META: Record<string, { icon: string; label: string; color: string }> = {
  pass: { icon: "🟢", label: "Замечаний нет", color: "text-success" },
  warning: { icon: "🟡", label: "Есть на что обратить внимание", color: "text-warning" },
  error: { icon: "🔴", label: "Требует исправлений", color: "text-error" },
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
          <span className="text-[18px] leading-none">{meta.icon}</span>
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
