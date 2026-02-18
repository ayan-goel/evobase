import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardView } from "@/app/dashboard/page";
import type { Repository } from "@/lib/types";

function makeRepo(overrides: Partial<Repository> = {}): Repository {
  return {
    id: "repo-1",
    github_repo_id: 123,
    default_branch: "main",
    package_manager: "npm",
    install_cmd: "npm ci",
    build_cmd: "npm run build",
    test_cmd: "npm test",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("DashboardView", () => {
  it("renders the page heading", () => {
    render(<DashboardView repos={[]} />);
    expect(screen.getByRole("heading", { name: "Repositories" })).toBeDefined();
  });

  it("shows empty state when no repos", () => {
    render(<DashboardView repos={[]} />);
    expect(screen.getByText(/No repositories connected/)).toBeDefined();
  });

  it("renders a repo card for each repo", () => {
    render(<DashboardView repos={[makeRepo(), makeRepo({ id: "repo-2", github_repo_id: 456 })]} />);
    expect(screen.getByText("Repo #123")).toBeDefined();
    expect(screen.getByText("Repo #456")).toBeDefined();
  });

  it("shows package manager in repo card", () => {
    render(<DashboardView repos={[makeRepo()]} />);
    // package_manager appears in the subtitle "main · npm"
    expect(screen.getByText(/main · npm/)).toBeDefined();
  });

  it("shows command chips when build/test cmds present", () => {
    render(<DashboardView repos={[makeRepo()]} />);
    expect(screen.getByText("npm run build")).toBeDefined();
    expect(screen.getByText("npm test")).toBeDefined();
  });

  it("repo card links to the repo page", () => {
    render(<DashboardView repos={[makeRepo({ id: "abc-123" })]} />);
    const link = screen.getByRole("link", { name: /Repo #123/i });
    expect(link.getAttribute("href")).toBe("/repos/abc-123");
  });

  it("uses id prefix when github_repo_id is null", () => {
    render(<DashboardView repos={[makeRepo({ github_repo_id: null })]} />);
    expect(screen.getByText(/Repo repo-1/)).toBeDefined();
  });

  it("shows connect repository button when repos empty", () => {
    render(<DashboardView repos={[]} />);
    const links = screen.getAllByRole("link", { name: /Connect Repository/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links.every((l) => l.getAttribute("href") === "/github/install")).toBe(true);
  });

  it("shows connect repository button in header", () => {
    render(<DashboardView repos={[makeRepo()]} />);
    const links = screen.getAllByRole("link", { name: /Connect Repository/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0].getAttribute("href")).toBe("/github/install");
  });

  it("shows setting up badge when latest run is queued", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "queued" })]}
      />,
    );
    expect(screen.getByText(/Setting up/i)).toBeInTheDocument();
  });

  it("shows setting up badge when latest run is running", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "running" })]}
      />,
    );
    expect(screen.getByText(/Setting up/i)).toBeInTheDocument();
  });

  it("shows no badge when latest run is completed", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "completed" })]}
      />,
    );
    expect(screen.queryByText(/Setting up/i)).not.toBeInTheDocument();
    // Arrow indicator should be present instead
    expect(screen.getByText("→")).toBeInTheDocument();
  });
});
