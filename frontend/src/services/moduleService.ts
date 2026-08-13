import { apiRequest } from "@/lib/apiClient";
import type { ModuleDefinition } from "@/types";

export const moduleService = {
  listActive: () => apiRequest<ModuleDefinition[]>("/api/v1/modules"),
  get: (id: string) => apiRequest<ModuleDefinition>(`/api/v1/modules/${id}`),
};
