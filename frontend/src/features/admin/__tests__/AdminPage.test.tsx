import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminPage } from "@/features/admin/AdminPage";
import { adminService } from "@/services/adminService";

vi.mock("@/services/adminService", () => ({
  adminService: {
    me: vi.fn(),
    dashboard: vi.fn(),
    users: vi.fn(),
    user: vi.fn(),
    blockUser: vi.fn(),
    unblockUser: vi.fn(),
    revokeSessions: vi.fn(),
    auditLog: vi.fn(),
  },
}));

const navigateMock = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

function renderAdminPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects non-admin users to home without rendering panel content", async () => {
    vi.mocked(adminService.me).mockResolvedValue({ is_admin: false });
    renderAdminPage();

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/", { replace: true }));
    expect(screen.queryByText("Админ-панель")).not.toBeInTheDocument();
  });

  it("renders the panel with role and permissions for an admin", async () => {
    vi.mocked(adminService.me).mockResolvedValue({
      is_admin: true,
      role_key: "owner",
      role_name: "Владелец",
      permissions: ["users.view", "users.block"],
    });
    vi.mocked(adminService.dashboard).mockResolvedValue({
      total_users: 3,
      blocked_users: 0,
      total_documents: 5,
      active_shares: 1,
      rate_limit_windows_last_hour: 2,
    });

    renderAdminPage();

    await waitFor(() => expect(screen.getByText("Админ-панель")).toBeInTheDocument());
    expect(screen.getByText("Владелец")).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("shows dashboard counts once loaded for an admin", async () => {
    vi.mocked(adminService.me).mockResolvedValue({
      is_admin: true,
      role_key: "owner",
      role_name: "Владелец",
      permissions: ["users.view"],
    });
    vi.mocked(adminService.dashboard).mockResolvedValue({
      total_users: 42,
      blocked_users: 1,
      total_documents: 7,
      active_shares: 2,
      rate_limit_windows_last_hour: 0,
    });

    renderAdminPage();

    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("Пользователей всего")).toBeInTheDocument();
  });

  it("shows a friendly error with retry when access check fails", async () => {
    vi.mocked(adminService.me).mockRejectedValue(new Error("network error"));
    renderAdminPage();

    await waitFor(() => expect(screen.getByText("Не удалось проверить права доступа.")).toBeInTheDocument());
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
