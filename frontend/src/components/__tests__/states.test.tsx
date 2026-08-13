import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingState } from "@/components/states/LoadingState";

describe("state components", () => {
  it("renders empty state with title and description", () => {
    render(<EmptyState title="Пусто" description="Ничего нет" />);
    expect(screen.getByText("Пусто")).toBeInTheDocument();
    expect(screen.getByText("Ничего нет")).toBeInTheDocument();
  });

  it("renders error state and calls retry on click", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Ошибка загрузки" onRetry={onRetry} />);
    expect(screen.getByText("Ошибка загрузки")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Повторить"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders loading state with status role", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("does not render retry button when onRetry is not provided", () => {
    render(<ErrorState message="Ошибка" />);
    expect(screen.queryByText("Повторить")).not.toBeInTheDocument();
  });
});
