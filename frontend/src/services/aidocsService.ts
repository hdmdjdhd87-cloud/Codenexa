import { apiRequest } from "@/lib/apiClient";

export interface AiDocsTemplateField {
  key: string;
  label: string;
  type: "text" | "textarea" | "date";
  required: boolean;
}

export interface AiDocsTemplate {
  id: string;
  template_key: string;
  name: string;
  category: string;
  description: string | null;
  fields_schema: AiDocsTemplateField[];
}

export interface AiDocsContentBlock {
  type: string;
  text: string;
}

export interface AiDocsDocument {
  id: string;
  title: string;
  doc_type: string;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  field_values?: Record<string, string>;
  content_blocks?: AiDocsContentBlock[];
}

export interface AiDocsVersion {
  id: string;
  version_number: number;
  note: string | null;
  created_at: string;
}

export interface AiDocsChatReply {
  conversation_id: string;
  reply: string;
  status: "idle" | "collecting" | "ready_to_create" | "done";
  quick_actions: string[];
  ready_to_create: boolean;
  document: AiDocsDocument | null;
}

export interface AiDocsConversation {
  id: string;
  status: string;
  messages: { role: "user" | "agent"; text: string; created_at: string }[];
}

export interface AiDocsShare {
  id: string;
  token: string;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface AiDocsWordDiffPart {
  op: "equal" | "insert" | "delete";
  text: string;
}

export interface AiDocsBlockDiff {
  op: "added" | "removed" | "unchanged" | "changed";
  type: string;
  old_text: string | null;
  new_text: string | null;
  old_index: number | null;
  new_index: number | null;
  word_diff: AiDocsWordDiffPart[];
}

export interface AiDocsVersionCompare {
  from: { version_number: number; created_at: string };
  to: { version_number: number; created_at: string };
  diff: {
    summary: { added: number; removed: number; changed: number; unchanged: number };
    blocks: AiDocsBlockDiff[];
  };
}

export interface AiDocsAnalysis {
  status: "pass" | "warning" | "error";
  disclaimer: string;
  issues: { severity: "error" | "warning" | "info"; category: string; message: string; suggestion: string | null }[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const aidocsService = {
  status: () => apiRequest<{ ai_available: boolean }>("/api/v1/aidocs/status"),
  templates: () => apiRequest<AiDocsTemplate[]>("/api/v1/aidocs/templates"),
  documents: (search?: string) =>
    apiRequest<AiDocsDocument[]>(`/api/v1/aidocs/documents${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  document: (id: string) => apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}`),
  versions: (id: string) => apiRequest<AiDocsVersion[]>(`/api/v1/aidocs/documents/${id}/versions`),
  restoreVersion: (id: string, versionId: string) =>
    apiRequest<{ document: AiDocsDocument; version: AiDocsVersion }>(
      `/api/v1/aidocs/documents/${id}/versions/${versionId}/restore`,
      { method: "POST" }
    ),
  compareVersions: (id: string, fromVersionId: string, toVersionId: string) =>
    apiRequest<AiDocsVersionCompare>(
      `/api/v1/aidocs/documents/${id}/versions/compare?from=${fromVersionId}&to=${toVersionId}`
    ),
  create: (payload: { template_id: string; title: string; field_values: Record<string, string> }) =>
    apiRequest<AiDocsDocument>("/api/v1/aidocs/documents", { method: "POST", body: payload }),
  remove: (id: string) => apiRequest<{ status: string }>(`/api/v1/aidocs/documents/${id}`, { method: "DELETE" }),
  setFavorite: (id: string, is_favorite: boolean) =>
    apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}/favorite`, { method: "PATCH", body: { is_favorite } }),
  rename: (id: string, title: string) =>
    apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}/rename`, { method: "PATCH", body: { title } }),
  duplicate: (id: string) => apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}/duplicate`, { method: "POST" }),
  createShare: (id: string, expires_in_days: number | null) =>
    apiRequest<AiDocsShare>(`/api/v1/aidocs/documents/${id}/share`, { method: "POST", body: { expires_in_days } }),
  listShares: (id: string) => apiRequest<AiDocsShare[]>(`/api/v1/aidocs/documents/${id}/shares`),
  revokeShare: (shareId: string) => apiRequest<{ status: string }>(`/api/v1/aidocs/shares/${shareId}`, { method: "DELETE" }),
  shareUrl: (token: string) => `${API_BASE_URL}/api/v1/aidocs/shared/${token}`,
  exportUrl: (id: string, format: "docx" | "pdf") => `${API_BASE_URL}/api/v1/aidocs/documents/${id}/export/${format}`,
  chat: (message: string, conversation_id?: string) =>
    apiRequest<AiDocsChatReply>("/api/v1/aidocs/chat", { method: "POST", body: { message, conversation_id } }),
  activeConversation: () => apiRequest<AiDocsConversation>("/api/v1/aidocs/conversations/active/current"),
  analyze: (id: string) => apiRequest<AiDocsAnalysis>(`/api/v1/aidocs/documents/${id}/analyze`, { method: "POST" }),
  async ocr(file: File): Promise<{ text: string; structural_understanding_available: boolean }> {
    const { getStoredToken } = await import("@/lib/tokenStorage");
    const token = getStoredToken();
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${API_BASE_URL}/api/v1/aidocs/ocr`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    const body = await resp.json().catch(() => null);
    if (!resp.ok) {
      throw new Error(body?.error?.message || "Не удалось распознать изображение.");
    }
    return body;
  },
  importDocument: async (file: File, title?: string): Promise<AiDocsDocument> => {
    const { getStoredToken } = await import("@/lib/tokenStorage");
    const token = getStoredToken();
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    const resp = await fetch(`${API_BASE_URL}/api/v1/aidocs/documents/import`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });
    const body = await resp.json().catch(() => null);
    if (!resp.ok) {
      throw new Error(body?.error?.message || "Не удалось импортировать документ.");
    }
    return body;
  },
};
