import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TriggerRunButton } from "@/components/trigger-run-button";

vi.mock("@/lib/api", () => ({
  triggerRun: vi.fn(),
}));

import { triggerRun } from "@/lib/api";
const mockTriggerRun = triggerRun as ReturnType<typeof vi.fn>;

describe("TriggerRunButton", () => {
  beforeEach(() => {
    mockTriggerRun.mockReset();
  });

  it("renders Trigger Run button in idle state", () => {
    render(<TriggerRunButton repoId="repo-1" />);
    expect(screen.getByRole("button", { name: "Trigger Run" })).toBeDefined();
  });

  it("shows loading state while the request is in flight", async () => {
    mockTriggerRun.mockReturnValue(new Promise(() => {}));

    render(<TriggerRunButton repoId="repo-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText(/Triggering/)).toBeDefined();
    });
  });

  it("button is disabled while loading", async () => {
    mockTriggerRun.mockReturnValue(new Promise(() => {}));

    render(<TriggerRunButton repoId="repo-1" />);
    const button = screen.getByRole("button");
    fireEvent.click(button);

    await waitFor(() => {
      expect(button.hasAttribute("disabled")).toBe(true);
    });
  });

  it("shows Queued state after a successful run is created", async () => {
    mockTriggerRun.mockResolvedValue({
      id: "run-abc-123",
      repo_id: "repo-1",
      status: "queued",
      sha: null,
      compute_minutes: null,
      created_at: new Date().toISOString(),
    });

    render(<TriggerRunButton repoId="repo-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText("Queued")).toBeDefined();
    });
  });

  it("calls onQueued callback with the new run id after success", async () => {
    const onQueued = vi.fn();
    mockTriggerRun.mockResolvedValue({
      id: "run-abc-123",
      repo_id: "repo-1",
      status: "queued",
      sha: null,
      compute_minutes: null,
      created_at: new Date().toISOString(),
    });

    render(<TriggerRunButton repoId="repo-1" onQueued={onQueued} />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(onQueued).toHaveBeenCalledWith("run-abc-123");
    });
  });

  it("shows error message on failure", async () => {
    mockTriggerRun.mockRejectedValue(new Error("Rate limit exceeded"));

    render(<TriggerRunButton repoId="repo-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText("Rate limit exceeded")).toBeDefined();
    });
  });

  it("returns to error state (button re-enabled) after failure", async () => {
    mockTriggerRun.mockRejectedValue(new Error("Network error"));

    render(<TriggerRunButton repoId="repo-1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      // Button text reverts to "Trigger Run" in error state
      expect(screen.getByRole("button", { name: "Trigger Run" })).toBeDefined();
    });
  });
});
