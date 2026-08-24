import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hideBackButton, showBackButton } from "@/lib/telegram";
import type { AiDocsTemplate, AiDocsConversation } from "@/services/aidocsService";
import { AiDocsHomeView } from "./views/HomeView";
import { DocumentListView } from "./views/DocumentListView";
import { ChatView } from "./views/ChatView";
import { TemplatesView } from "./views/TemplatesView";
import { CreateDocumentView } from "./views/CreateDocumentView";
import { DocumentPreviewView } from "./views/DocumentPreviewView";

type View = "home" | "list" | "templates" | "create" | "preview" | "chat" | "edit_chat";

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
