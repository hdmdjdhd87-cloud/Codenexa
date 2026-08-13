import { apiRequest } from "@/lib/apiClient";
import type { UserSettings } from "@/types";

export const settingsService = {
  get: () => apiRequest<UserSettings>("/api/v1/settings"),
  update: (patch: Partial<Pick<UserSettings, "language" | "theme" | "haptic_feedback" | "notifications_enabled">>) =>
    apiRequest<UserSettings>("/api/v1/settings", { method: "PATCH", body: patch }),
};
