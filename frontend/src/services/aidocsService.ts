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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const aidocsService = {
  status: () => apiRequest<{ ai_available: boolean }>("/api/v1/aidocs/status"),
  templates: () => apiRequest<AiDocsTemplate[]>("/api/v1/aidocs/templates"),
  documents: () => apiRequest<AiDocsDocument[]>("/api/v1/aidocs/documents"),
  document: (id: string) => apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}`),
  versions: (id: string) => apiRequest<AiDocsVersion[]>(`/api/v1/aidocs/documents/${id}/versions`),
  create: (payload: { template_id: string; title: string; field_values: Record<string, string> }) =>
    apiRequest<AiDocsDocument>("/api/v1/aidocs/documents", { method: "POST", body: payload }),
  remove: (id: string) => apiRequest<{ status: string }>(`/api/v1/aidocs/documents/${id}`, { method: "DELETE" }),
  setFavorite: (id: string, is_favorite: boolean) =>
    apiRequest<AiDocsDocument>(`/api/v1/aidocs/documents/${id}/favorite`, { method: "PATCH", body: { is_favorite } }),
  exportUrl: (id: string, format: "docx" | "pdf") => `${API_BASE_URL}/api/v1/aidocs/documents/${id}/export/${format}`,
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
};
