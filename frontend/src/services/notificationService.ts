import { apiRequest } from "@/lib/apiClient";
import type { NotificationItem } from "@/types";

export const notificationService = {
  list: () => apiRequest<NotificationItem[]>("/api/v1/notifications"),
  markRead: (id: string) => apiRequest<{ status: string }>(`/api/v1/notifications/${id}/read`, { method: "POST" }),
  markAllRead: () => apiRequest<{ status: string }>("/api/v1/notifications/read-all", { method: "POST" }),
};
