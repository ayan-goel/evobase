import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { RepoRunList } from "@/components/repo-run-list";
import type { Proposal, Run } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getRuns: vi.fn(),
  getProposalsByRun: vi.fn(),
}));

// Silence OnboardingBanner and ProposalCard to keep tests focused
vi.mock("@/components/onboarding-banner", () => ({
  OnboardingBanner: () => null,
}));
vi.mock("@/components/proposal-card", () => ({
  ProposalCard: ({ proposal }: { proposal: Proposal }) => (
    <div data-testid="proposal-card">{proposal.summary}</div>
  ),
}));

import { getRuns, getProposalsByRun } from "@/lib/api";
const mockGetRuns = getRuns as ReturnType<typeof vi.fn>;
const mockGetProposalsByRun = getProposalsByRun as ReturnType<typeof vi.fn>;

function makeRun(
  status: Run["status"],
  overrides: Partial<Run> = {},
): Run & { proposals: Proposal[] } {
  return {
    id: "run-1",
    repo_id: "repo-1",
    sha: "abc1234",
    status,
    compute_minutes: null,
    created_at: new Date().toISOString(),
    proposals: [],
    ...overrides,
  };
}

describe("RepoRunList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGetRuns.mockReset();
    mockGetProposalsByRun.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders initial runs from server without polling", () => {
    const initialRuns = [
      makeRun("completed", { id: "run-a", sha: "aaa1111" }),
      makeRun("failed", { id: "run-b", sha: "bbb2222" }),
    ];

    render(<RepoRunList repoId="repo-1" initialRuns={initialRuns} />);

    // Both run SHAs should be visible
    expect(screen.getByText("aaa1111")).toBeDefined();
    expect(screen.getByText("bbb2222")).toBeDefined();
    // No API calls made — all runs are terminal
    expect(mockGetRuns).not.toHaveBeenCalled();
  });

  it("shows the trigger run button", () => {
    render(<RepoRunList repoId="repo-1" initialRuns={[]} />);

    expect(screen.getByRole("button", { name: /Trigger Run/i })).toBeDefined();
  });

  it("updates run status after a poll tick", async () => {
    const initialRuns = [makeRun("queued", { id: "run-1", sha: "start11" })];

    // Poll returns the run as "running"
    mockGetRuns.mockResolvedValue([
      makeRun("running", { id: "run-1", sha: "start11" }),
    ]);
    mockGetProposalsByRun.mockResolvedValue([]);

    render(<RepoRunList repoId="repo-1" initialRuns={initialRuns} />);

    // Initial state shows "queued"
    expect(screen.getByText("queued")).toBeDefined();

    await act(async () => {
      vi.advanceTimersByTime(5_000);
      // Let async work (getRuns + getProposalsByRun) settle
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("running")).toBeDefined();
  });
});
