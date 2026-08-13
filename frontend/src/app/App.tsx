import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthGate } from "./AuthGate";
import { BottomNav } from "@/components/BottomNav";
import { HomePage } from "@/features/home/HomePage";
import { CatalogPage } from "@/features/catalog/CatalogPage";
import { FavoritesPage } from "@/features/favorites/FavoritesPage";
import { HistoryPage } from "@/features/history/HistoryPage";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";
import { ProfilePage } from "@/features/profile/ProfilePage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { ModuleRoutePage } from "@/features/moduleRoute/ModuleRoutePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function AppShell() {
  return (
    <div className="min-h-screen pb-[64px]">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/apps/:moduleKey" element={<ModuleRoutePage />} />
      </Routes>
      <BottomNav />
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthGate>
          <AppShell />
        </AuthGate>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
