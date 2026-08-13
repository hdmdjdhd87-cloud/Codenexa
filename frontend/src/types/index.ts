export type ModuleStatus = "active" | "disabled" | "maintenance";

export interface ModuleDefinition {
  id: string;
  module_key: string;
  name: string;
  slug: string;
  description: string | null;
  category: string | null;
  icon: string | null;
  route: string | null;
  version: string;
  status: ModuleStatus;
  is_featured: boolean;
  sort_order: number;
}

export interface NexaUser {
  id: string;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  language_code: string | null;
  photo_url: string | null;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
}

export interface FavoriteItem {
  id: string;
  module_id: string;
  created_at: string;
  module_key: string;
  name: string;
  description: string | null;
  category: string | null;
  icon: string | null;
  route: string | null;
  status: ModuleStatus;
}

export interface HistoryItem {
  id: string;
  action: string;
  metadata: Record<string, unknown>;
  created_at: string;
  module_id: string | null;
  module_name: string | null;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  module_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface UserSettings {
  id: string;
  user_id: string;
  language: string;
  theme: "system" | "dark" | "light";
  haptic_feedback: boolean;
  notifications_enabled: boolean;
  settings_json: Record<string, unknown>;
}

export interface ApiErrorBody {
  error: { code: string; message: string };
}
