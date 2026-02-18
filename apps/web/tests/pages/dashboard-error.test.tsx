import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DashboardError from "@/app/dashboard/error";

describe("DashboardError", () => {
  it("renders the error boundary container", () => {
    render(<DashboardError error={new Error("Test error")} reset={() => {}} />);
    expect(screen.getByTestId("dashboard-error")).toBeDefined();
  });

  it("shows 'Something went wrong' message", () => {
    render(<DashboardError error={new Error("Test error")} reset={() => {}} />);
    expect(screen.getByText(/something went wrong/i)).toBeDefined();
  });

  it("shows the error message detail", () => {
    render(<DashboardError error={new Error("API unavailable")} reset={() => {}} />);
    expect(screen.getByText("API unavailable")).toBeDefined();
  });

  it("calls reset when Try again is clicked", () => {
    const reset = vi.fn();
    render(<DashboardError error={new Error("oops")} reset={reset} />);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
