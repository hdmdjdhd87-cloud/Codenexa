import { useState } from "react";
import { haptic } from "@/lib/telegram";
import { useAiDocsDocuments, useAiDocsActiveConversation } from "../hooks";
import type { AiDocsConversation } from "@/services/aidocsService";
import { formatDate } from "../shared";

export function AiDocsHomeView({
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

  // useInfiniteQuery по умолчанию грузит только первую страницу — Home
  // не вызывает fetchNextPage, так что здесь ровно то же поведение, что
  // было раньше с плоским useQuery (счётчики по первой странице, не
  // истинный global count при >page_size документов — та же
  // ограниченность, что и до перехода на pagination, не регрессия).
  const allDocs = documents.data?.pages.flat() ?? [];
  const total = allDocs.length;
  const favoritesCount = allDocs.filter((d) => d.is_favorite).length;
  const lastDoc = allDocs[0]; // список уже отсортирован backend'ом по updated_at desc

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
