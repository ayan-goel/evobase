import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRunPolling } from "@/lib/hooks/use-run-polling";
import type { Run } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getRuns: vi.fn(),
}));

import { getRuns } from "@/lib/api";
const mockGetRuns = getRuns as ReturnType<typeof vi.fn>;

function makeRun(status: Run["status"], id = "run-1"): Run {
  return {
    id,
    repo_id: "repo-1",
    sha: "abc1234",
    status,
    compute_minutes: null,
    failure_step: null,
    commit_message: null,
    created_at: new Date().toISOString(),
  };
}

describe("useRunPolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetRuns.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not poll when all runs are completed", async () => {
    const initialRuns = [makeRun("completed")];
    renderHook(() => useRunPolling("repo-1", initialRuns));

    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });

    expect(mockGetRuns).not.toHaveBeenCalled();
  });

  it("does not poll when all runs are failed", async () => {
    const initialRuns = [makeRun("failed")];
    renderHook(() => useRunPolling("repo-1", initialRuns));

    await act(async () => {
      vi.advanceTimersByTime(10_000);
    });

    expect(mockGetRuns).not.toHaveBeenCalled();
  });

  it("starts polling when a run is queued", async () => {
    const initialRuns = [makeRun("queued")];
    mockGetRuns.mockResolvedValue([makeRun("queued")]);

    renderHook(() => useRunPolling("repo-1", initialRuns));

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(mockGetRuns).toHaveBeenCalledWith("repo-1");
  });

  it("starts polling when a run is running", async () => {
    const initialRuns = [makeRun("running")];
    mockGetRuns.mockResolvedValue([makeRun("running")]);

    renderHook(() => useRunPolling("repo-1", initialRuns));

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(mockGetRuns).toHaveBeenCalledWith("repo-1");
  });

  it("stops polling when runs transition to terminal", async () => {
    const initialRuns = [makeRun("running")];
    // First poll returns completed
    mockGetRuns.mockResolvedValue([makeRun("completed")]);

    renderHook(() => useRunPolling("repo-1", initialRuns));

    // Advance through first tick
    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(mockGetRuns).toHaveBeenCalledTimes(1);

    // Advance through a second potential tick — should not fire again
    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(mockGetRuns).toHaveBeenCalledTimes(1);
  });

  it("updates runs state from poll response", async () => {
    const initialRuns = [makeRun("queued")];
    const updatedRun = makeRun("running");
    mockGetRuns.mockResolvedValue([updatedRun]);

    const { result } = renderHook(() => useRunPolling("repo-1", initialRuns));

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(result.current[0].status).toBe("running");
  });

  it("cleans up interval on unmount", async () => {
    const initialRuns = [makeRun("queued")];
    mockGetRuns.mockResolvedValue([makeRun("queued")]);

    const { unmount } = renderHook(() => useRunPolling("repo-1", initialRuns));

    unmount();

    // Advance past the interval — getRuns should not have been called
    await act(async () => {
      vi.advanceTimersByTime(5_000);
      await Promise.resolve();
    });

    expect(mockGetRuns).not.toHaveBeenCalled();
  });
});
