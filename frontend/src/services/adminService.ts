import { apiRequest } from "@/lib/apiClient";

export interface AdminMe {
  is_admin: boolean;
  role_key?: string;
  role_name?: string;
  permissions?: string[];
}

export interface AdminDashboard {
  total_users: number;
  blocked_users: number;
  total_documents: number;
  active_shares: number;
  rate_limit_windows_last_hour: number;
}

export interface AdminUser {
  id: string;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  is_blocked: boolean;
  blocked_at?: string | null;
  blocked_reason: string | null;
  created_at: string;
  last_seen_at: string | null;
}

export interface AdminAuditLogEntry {
  id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  reason: string | null;
  before_json: Record<string, unknown>;
  after_json: Record<string, unknown>;
  created_at: string;
  actor_username: string | null;
  actor_telegram_id: number | null;
}

export const adminService = {
  me: () => apiRequest<AdminMe>("/api/v1/admin/me"),
  dashboard: () => apiRequest<AdminDashboard>("/api/v1/admin/dashboard"),
  users: (search?: string, page = 1) =>
    apiRequest<AdminUser[]>(
      `/api/v1/admin/users?page=${page}${search ? `&search=${encodeURIComponent(search)}` : ""}`
    ),
  user: (id: string) => apiRequest<AdminUser>(`/api/v1/admin/users/${id}`),
  blockUser: (id: string, reason: string) =>
    apiRequest<AdminUser>(`/api/v1/admin/users/${id}/block`, { method: "POST", body: { reason } }),
  unblockUser: (id: string) => apiRequest<AdminUser>(`/api/v1/admin/users/${id}/unblock`, { method: "POST" }),
  revokeSessions: (id: string) =>
    apiRequest<{ id: string; sessions_valid_from: string }>(`/api/v1/admin/users/${id}/revoke-sessions`, {
      method: "POST",
    }),
  auditLog: (page = 1) => apiRequest<AdminAuditLogEntry[]>(`/api/v1/admin/audit-log?page=${page}`),
};
