import { apiRequest } from "@/lib/apiClient";
import type { HistoryItem } from "@/types";

export const historyService = {
  list: (page = 1) => apiRequest<HistoryItem[]>(`/api/v1/history?page=${page}`),
};
