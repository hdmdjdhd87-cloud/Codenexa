import { apiRequest } from "@/lib/apiClient";
import type { NexaUser } from "@/types";

export const userService = {
  me: () => apiRequest<NexaUser>("/api/v1/users/me"),
};
