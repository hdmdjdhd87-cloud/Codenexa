import { apiRequest } from "@/lib/apiClient";
import type { FavoriteItem } from "@/types";

export const favoriteService = {
  list: () => apiRequest<FavoriteItem[]>("/api/v1/favorites"),
  add: (moduleId: string) => apiRequest<FavoriteItem>("/api/v1/favorites", { method: "POST", body: { module_id: moduleId } }),
  remove: (moduleId: string) => apiRequest<{ status: string }>(`/api/v1/favorites/${moduleId}`, { method: "DELETE" }),
};
