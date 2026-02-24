import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RepoView } from "@/app/repos/[repoId]/page";
import type { Proposal, Repository, Run } from "@/lib/types";

vi.mock("@/lib/hooks/use-run-events", () => ({
  useRunEvents: () => ({
    events: [],
    currentPhase: null,
    isConnected: false,
    isDone: false,
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    deleteRun: vi.fn().mockResolvedValue(undefined),
  };
});

function makeRepo(overrides: Partial<Repository> = {}): Repository {
  return {
    id: "repo-1",
    github_repo_id: 123,
    github_full_name: null,
    default_branch: "main",
    package_manager: "npm",
    framework: null,
    install_cmd: "npm ci",
    build_cmd: null,
    test_cmd: "npm test",
    typecheck_cmd: null,
    root_dir: null,
    setup_failing: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeRun(
  status: Run["status"] = "completed",
  proposals: Proposal[] = [],
): Run & { proposals: Proposal[] } {
  return {
    id: "run-1",
    repo_id: "repo-1",
    sha: "abc1234",
    status,
    compute_minutes: null,
    failure_step: null,
    commit_message: null,
    created_at: new Date().toISOString(),
    proposals,
  };
}

function makeProposal(): Proposal {
  return {
    id: "prop-1",
    run_id: "run-1",
    repo_id: "repo-1",
    diff: "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-x\n+y\n",
    summary: "Optimized set membership check",
    metrics_before: null,
    metrics_after: null,
    risk_score: 0.2,
    confidence: "high",
    created_at: new Date().toISOString(),
    pr_url: null,
    framework: null,
    patch_variants: [],
    selection_reason: null,
    approaches_tried: null,
    artifacts: [],
    discovery_trace: null,
    patch_trace: null,
  };
}

describe("RepoView", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders repo heading with github_repo_id when github_full_name is absent", () => {
    render(<RepoView repo={makeRepo()} runs={[]} />);
    expect(screen.getByRole("heading", { name: "Repo #123" })).toBeDefined();
  });

  it("prefers github_full_name over repo_id and numeric id", () => {
    render(
      <RepoView
        repo={makeRepo({ github_full_name: "acme/api-service" })}
        runs={[]}
      />,
    );
    expect(screen.getByRole("heading", { name: "acme/api-service" })).toBeDefined();
  });

  it("falls back to short UUID when neither github_full_name nor github_repo_id are set", () => {
    render(
      <RepoView
        repo={makeRepo({ github_full_name: null, github_repo_id: null })}
        runs={[]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Repo repo-1" })).toBeDefined();
  });

  it("shows empty state when no runs", () => {
    render(<RepoView repo={makeRepo()} runs={[]} />);
    expect(screen.getByText(/No runs yet/)).toBeDefined();
  });

  it("renders run status badge", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun("completed")]} />);
    expect(screen.getByText("completed")).toBeDefined();
  });

  it("renders run SHA", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    expect(screen.getByText("abc1234")).toBeDefined();
  });

  it("shows live status summary for running run with no proposals", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun("running", [])]} />);
    expect(screen.getByText(/Starting up/)).toBeDefined();
    expect(screen.getByText(/View live details/)).toBeDefined();
  });

  it("renders proposal cards within the run", () => {
    render(
      <RepoView
        repo={makeRepo()}
        runs={[makeRun("completed", [makeProposal()])]}
      />,
    );
    expect(screen.getByText("Optimized set membership check")).toBeDefined();
  });

  it("renders breadcrumb with Dashboard link", () => {
    render(<RepoView repo={makeRepo()} runs={[]} />);
    const link = screen.getByRole("link", { name: "Dashboard" });
    expect(link.getAttribute("href")).toBe("/dashboard");
  });

  it("shows meta row with proposal count and confidence for completed runs", () => {
    render(
      <RepoView
        repo={makeRepo()}
        runs={[makeRun("completed", [makeProposal()])]}
      />,
    );
    expect(screen.getByText(/1 proposal/)).toBeDefined();
  });

  it("shows 'No opportunities' in meta row for completed run with no proposals", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun("completed", [])]} />);
    expect(screen.getByText("No opportunities")).toBeDefined();
  });

  it("shows compute time in meta row when available", () => {
    const run = { ...makeRun("completed"), compute_minutes: 3.2 };
    render(<RepoView repo={makeRepo()} runs={[run]} />);
    expect(screen.getByText(/3\.2 min compute/)).toBeDefined();
  });

  // ---------------------------------------------------------------------------
  // Select / delete flow
  // ---------------------------------------------------------------------------

  it("shows Select button when there are runs", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    expect(screen.getByRole("button", { name: "Select" })).toBeDefined();
  });

  it("does not show Select button when there are no runs", () => {
    render(<RepoView repo={makeRepo()} runs={[]} />);
    expect(screen.queryByRole("button", { name: "Select" })).toBeNull();
  });

  it("shows Cancel button and Delete button (disabled) after clicking Select", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));

    expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    const deleteBtn = screen.getByRole("button", { name: /Delete/ });
    expect(deleteBtn).toBeDefined();
    expect((deleteBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("hides Select button and shows checkboxes when in select mode", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));

    expect(screen.queryByRole("button", { name: "Select" })).toBeNull();
    expect(screen.getByRole("button", { name: /Select run|Deselect run/ })).toBeDefined();
  });

  it("enables Delete button after checking a run", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));

    fireEvent.click(screen.getByRole("button", { name: "Select run" }));

    const deleteBtn = screen.getByRole("button", { name: /Delete \(1\)/ });
    expect((deleteBtn as HTMLButtonElement).disabled).toBe(false);
  });

  it("clicking Cancel exits select mode and hides checkboxes", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: "Select" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("shows confirmation dialog with correct count when Delete is clicked", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    fireEvent.click(screen.getByRole("button", { name: "Select run" }));
    fireEvent.click(screen.getByRole("button", { name: /Delete \(1\)/ }));

    expect(screen.getByText(/Are you sure you want to delete/)).toBeDefined();
    expect(screen.getByText(/1 run/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Yes, delete" })).toBeDefined();
  });

  it("closes confirmation dialog when Cancel is clicked inside it", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    fireEvent.click(screen.getByRole("button", { name: "Select run" }));
    fireEvent.click(screen.getByRole("button", { name: /Delete \(1\)/ }));

    // click the Cancel inside the dialog (there may be two "Cancel" buttons)
    const cancelBtns = screen.getAllByRole("button", { name: "Cancel" });
    fireEvent.click(cancelBtns[cancelBtns.length - 1]);

    expect(screen.queryByText(/Are you sure you want to delete/)).toBeNull();
  });

  it("calls deleteRun and removes run from list after confirming delete", async () => {
    const { deleteRun: mockDeleteRun } = await import("@/lib/api");
    render(<RepoView repo={makeRepo()} runs={[makeRun()]} />);
    fireEvent.click(screen.getByRole("button", { name: "Select" }));
    fireEvent.click(screen.getByRole("button", { name: "Select run" }));
    fireEvent.click(screen.getByRole("button", { name: /Delete \(1\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));

    await waitFor(() => {
      expect(mockDeleteRun).toHaveBeenCalledWith("run-1");
    });

    await waitFor(() => {
      expect(screen.queryByText("abc1234")).toBeNull();
    });
  });
});
