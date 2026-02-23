import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RepoView } from "@/app/repos/[repoId]/page";
import type { Proposal, Repository, Run } from "@/lib/types";

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
    artifacts: [],
  };
}

describe("RepoView", () => {
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

  it("shows live progress link for running run with no proposals", () => {
    render(<RepoView repo={makeRepo()} runs={[makeRun("running", [])]} />);
    expect(screen.getByText(/View live progress/)).toBeDefined();
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
});
