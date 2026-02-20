import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

const mockDetectFramework = vi.fn();

vi.mock("@/lib/api", () => ({
  detectFramework: (...args: any[]) => mockDetectFramework(...args),
}));

import { useDetectFramework } from "@/hooks/use-detect-framework";

describe("useDetectFramework", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not call API when repoFullName is null", async () => {
    renderHook(() => useDetectFramework(42, null, ""));
    await act(async () => {
      vi.advanceTimersByTime(600);
    });
    expect(mockDetectFramework).not.toHaveBeenCalled();
  });

  it("does not call API before 500ms debounce elapses", async () => {
    renderHook(() => useDetectFramework(42, "owner/repo", ""));
    await act(async () => {
      vi.advanceTimersByTime(400);
    });
    expect(mockDetectFramework).not.toHaveBeenCalled();
  });

  it("calls API after 500ms debounce elapses", async () => {
    mockDetectFramework.mockResolvedValue({
      framework: "nextjs",
      language: "javascript",
      package_manager: "npm",
      confidence: 0.9,
    });

    renderHook(() => useDetectFramework(42, "owner/repo", ""));
    await act(async () => {
      vi.advanceTimersByTime(500);
    });

    expect(mockDetectFramework).toHaveBeenCalledWith(42, "owner/repo", null);
  });

  it("returns detection result after successful API call", async () => {
    const expected = {
      framework: "nextjs",
      language: "javascript",
      package_manager: "pnpm",
      confidence: 0.9,
    };
    mockDetectFramework.mockResolvedValue(expected);

    const { result } = renderHook(() => useDetectFramework(42, "owner/repo", ""));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve(); // flush microtasks
    });

    expect(result.current.result).toEqual(expected);
    expect(result.current.isDetecting).toBe(false);
  });

  it("clears result when repo is deselected (repoFullName → null)", async () => {
    const expected = {
      framework: "nextjs",
      language: "javascript",
      package_manager: "npm",
      confidence: 0.9,
    };
    mockDetectFramework.mockResolvedValue(expected);

    const { result, rerender } = renderHook(
      ({ repoFullName }: { repoFullName: string | null }) =>
        useDetectFramework(42, repoFullName, ""),
      { initialProps: { repoFullName: "owner/repo" as string | null } },
    );

    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });

    expect(result.current.result).toEqual(expected);

    // Deselect the repo
    rerender({ repoFullName: null });

    expect(result.current.result).toBeNull();
  });

  it("passes rootDir to the API call", async () => {
    mockDetectFramework.mockResolvedValue({
      framework: "fastapi",
      language: "python",
      package_manager: "uv",
      confidence: 0.85,
    });

    renderHook(() => useDetectFramework(42, "owner/monorepo", "apps/api"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });

    expect(mockDetectFramework).toHaveBeenCalledWith(42, "owner/monorepo", "apps/api");
  });

  it("sets result to null on API error", async () => {
    mockDetectFramework.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useDetectFramework(42, "owner/repo", ""));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });

    expect(result.current.result).toBeNull();
    expect(result.current.isDetecting).toBe(false);
  });
});
