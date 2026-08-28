import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { haptic } from "@/lib/telegram";
import { aidocsService, type AiDocsConversation } from "@/services/aidocsService";

interface ChatMessage {
  role: "user" | "agent";
  text: string;
}

export function ChatView({
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
          <button onClick={() => onDocumentEdited(documentId)} className="text-accent text-cn-sm font-semibold">
            Готово, вернуться к документу
          </button>
        </div>
      )}
      <div ref={scrollRef} className="flex-1 overflow-y-auto flex flex-col gap-2.5 pb-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-cn-base leading-relaxed whitespace-pre-line ${
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
          className="flex-1 rounded-xl bg-surface border border-border px-3.5 py-2.5 text-cn-base text-text-primary placeholder:text-text-secondary outline-none resize-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="shrink-0 w-10 h-10 rounded-xl bg-accent text-white font-semibold disabled:opacity-50 flex items-center justify-center"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
