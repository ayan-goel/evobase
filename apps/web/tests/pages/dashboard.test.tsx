import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardView } from "@/app/dashboard/page";
import type { Installation, Repository } from "@/lib/types";

function makeRepo(overrides: Partial<Repository> = {}): Repository {
  return {
    id: "repo-1",
    github_repo_id: 123,
    default_branch: "main",
    package_manager: "npm",
    install_cmd: "npm ci",
    build_cmd: "npm run build",
    test_cmd: "npm test",
    typecheck_cmd: null,
    root_dir: null,
    setup_failing: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeInstallation(
  overrides: Partial<Installation> = {},
): Installation {
  return {
    id: "inst-1",
    installation_id: 12345678,
    account_login: "octocat",
    account_id: 1,
    ...overrides,
  };
}

describe("DashboardView", () => {
  it("renders the page heading", () => {
    render(<DashboardView repos={[]} installations={[]} />);
    expect(screen.getByRole("heading", { name: "Repositories" })).toBeDefined();
  });

  it("shows empty state when no repos and no installations", () => {
    render(<DashboardView repos={[]} installations={[]} />);
    expect(screen.getByText(/No repositories connected/)).toBeDefined();
  });

  it("shows resume setup banner when installations exist but no repos", () => {
    render(
      <DashboardView repos={[]} installations={[makeInstallation()]} />,
    );
    expect(screen.getByText(/finish setting up your repositories/i)).toBeDefined();
    const link = screen.getByRole("link", { name: /Select Repositories/i });
    expect(link.getAttribute("href")).toContain("12345678");
  });

  it("renders a repo card for each repo", () => {
    render(
      <DashboardView
        repos={[makeRepo(), makeRepo({ id: "repo-2", github_repo_id: 456 })]}
        installations={[]}
      />,
    );
    expect(screen.getByText("Repo #123")).toBeDefined();
    expect(screen.getByText("Repo #456")).toBeDefined();
  });

  it("shows package manager in repo card", () => {
    render(<DashboardView repos={[makeRepo()]} installations={[]} />);
    expect(screen.getByText(/main · npm/)).toBeDefined();
  });

  it("shows command chips when build/test cmds present", () => {
    render(<DashboardView repos={[makeRepo()]} installations={[]} />);
    expect(screen.getByText("npm run build")).toBeDefined();
    expect(screen.getByText("npm test")).toBeDefined();
  });

  it("repo card links to the repo page", () => {
    render(<DashboardView repos={[makeRepo({ id: "abc-123" })]} installations={[]} />);
    const link = screen.getByRole("link", { name: /Repo #123/i });
    expect(link.getAttribute("href")).toBe("/repos/abc-123");
  });

  it("uses id prefix when github_repo_id is null", () => {
    render(
      <DashboardView repos={[makeRepo({ github_repo_id: null })]} installations={[]} />,
    );
    expect(screen.getByText(/Repo repo-1/)).toBeDefined();
  });

  it("shows connect repository button when repos empty and no installations", () => {
    render(<DashboardView repos={[]} installations={[]} />);
    const links = screen.getAllByRole("link", { name: /Connect Repository/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links.every((l) => l.getAttribute("href") === "/github/install")).toBe(true);
  });

  it("shows connect repository button in header", () => {
    render(<DashboardView repos={[makeRepo()]} installations={[]} />);
    const links = screen.getAllByRole("link", { name: /Connect Repository/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links[0].getAttribute("href")).toBe("/github/install");
  });

  it("shows setting up badge when latest run is queued", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "queued" })]}
        installations={[]}
      />,
    );
    expect(screen.getByText(/Setting up/i)).toBeInTheDocument();
  });

  it("shows setting up badge when latest run is running", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "running" })]}
        installations={[]}
      />,
    );
    expect(screen.getByText(/Setting up/i)).toBeInTheDocument();
  });

  it("shows no badge when latest run is completed", () => {
    render(
      <DashboardView
        repos={[makeRepo({ latest_run_status: "completed" })]}
        installations={[]}
      />,
    );
    expect(screen.queryByText(/Setting up/i)).not.toBeInTheDocument();
    expect(screen.getByText("→")).toBeInTheDocument();
  });
});
