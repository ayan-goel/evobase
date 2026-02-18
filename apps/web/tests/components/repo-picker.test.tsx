import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockGetInstallationRepos = vi.fn();
const mockGetMe = vi.fn();
const mockConnectRepo = vi.fn();
const mockPush = vi.fn();

vi.mock("@/lib/api", () => ({
  getInstallationRepos: (...args: any[]) => mockGetInstallationRepos(...args),
  getMe: (...args: any[]) => mockGetMe(...args),
  connectRepo: (...args: any[]) => mockConnectRepo(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import { RepoPicker } from "@/components/repo-picker";

describe("RepoPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetMe.mockResolvedValue({ user_id: "user-1", org_id: "test-org-id" });
  });

  it("renders loading state", () => {
    mockGetInstallationRepos.mockImplementation(
      () => new Promise(() => {}), // never resolves
    );
    render(<RepoPicker installationId={42000} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders repo list with checkboxes", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
      { github_repo_id: 2, full_name: "org/repo2", name: "repo2", default_branch: "main", private: true },
      { github_repo_id: 3, full_name: "org/repo3", name: "repo3", default_branch: "develop", private: false },
    ]);

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });

    expect(screen.getByText("org/repo2")).toBeInTheDocument();
    expect(screen.getByText("org/repo3")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
  });

  it("connect button disabled when no repos selected", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
    ]);

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });

    const button = screen.getByRole("button", { name: /connect 0 repos/i });
    expect(button).toBeDisabled();
  });

  it("connect button enabled when repos selected", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
    ]);

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("checkbox"));

    const button = screen.getByRole("button", { name: /connect 1 repo$/i });
    expect(button).not.toBeDisabled();
  });

  it("calls connectRepo for each selected repo", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
      { github_repo_id: 2, full_name: "org/repo2", name: "repo2", default_branch: "main", private: false },
    ]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    fireEvent.click(screen.getByRole("button", { name: /connect 2 repos/i }));

    await waitFor(() => {
      expect(mockConnectRepo).toHaveBeenCalledTimes(2);
    });
  });

  it("shows success state after connection", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
    ]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /connect 1 repo$/i }));

    await waitFor(() => {
      expect(screen.getByText(/connected successfully/i)).toBeInTheDocument();
    });
  });

  it("shows error on API failure", async () => {
    mockGetInstallationRepos.mockRejectedValue(new Error("GitHub API down"));

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("GitHub API down")).toBeInTheDocument();
    });
  });
});
