import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockGetInstallationRepos = vi.fn();
const mockGetMe = vi.fn();
const mockConnectRepo = vi.fn();
const mockUseDetectFramework = vi.fn();
const mockPush = vi.fn();

vi.mock("@/lib/api", () => ({
  getInstallationRepos: (...args: any[]) => mockGetInstallationRepos(...args),
  getMe: (...args: any[]) => mockGetMe(...args),
  connectRepo: (...args: any[]) => mockConnectRepo(...args),
}));

vi.mock("@/hooks/use-detect-framework", () => ({
  useDetectFramework: (...args: any[]) => mockUseDetectFramework(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import { RepoPicker } from "@/components/repo-picker";

const REPOS = [
  { github_repo_id: 1, full_name: "org/repo1", name: "repo1", default_branch: "main", private: false },
  { github_repo_id: 2, full_name: "org/repo2", name: "repo2", default_branch: "main", private: true },
  { github_repo_id: 3, full_name: "org/repo3", name: "repo3", default_branch: "develop", private: false },
];

describe("RepoPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetMe.mockResolvedValue({ user_id: "user-1", org_id: "test-org-id" });
    mockUseDetectFramework.mockReturnValue({ result: null, isDetecting: false });
  });

  // ─── Loading ────────────────────────────────────────────────────────────────

  it("renders loading state", () => {
    mockGetInstallationRepos.mockImplementation(() => new Promise(() => {}));
    render(<RepoPicker installationId={42000} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ─── Repo list ──────────────────────────────────────────────────────────────

  it("renders repo list", async () => {
    mockGetInstallationRepos.mockResolvedValue(REPOS);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("org/repo1")).toBeInTheDocument();
    });
    expect(screen.getByText("org/repo2")).toBeInTheDocument();
    expect(screen.getByText("org/repo3")).toBeInTheDocument();

    // Custom checkboxes are styled divs, not native inputs
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });

  // ─── Connect button state ────────────────────────────────────────────────────

  it("connect button is disabled when nothing is selected", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    const button = screen.getByRole("button", { name: /connect 0 projects/i });
    expect(button).toBeDisabled();
  });

  it("connect button is enabled after selecting a repo", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));

    const button = screen.getByRole("button", { name: /connect 1 project$/i });
    expect(button).not.toBeDisabled();
  });

  it("deselecting a repo removes it from the count", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1")); // select
    expect(screen.getByRole("button", { name: /connect 1 project$/i })).not.toBeDisabled();

    fireEvent.click(screen.getByText("org/repo1")); // deselect
    expect(screen.getByRole("button", { name: /connect 0 projects/i })).toBeDisabled();
  });

  // ─── Connecting ─────────────────────────────────────────────────────────────

  it("calls connectRepo once per selected repo", async () => {
    mockGetInstallationRepos.mockResolvedValue(REPOS.slice(0, 2));
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByText("org/repo2"));

    fireEvent.click(screen.getByRole("button", { name: /connect 2 projects/i }));

    await waitFor(() => {
      expect(mockConnectRepo).toHaveBeenCalledTimes(2);
    });
    expect(mockConnectRepo).toHaveBeenCalledWith(
      expect.objectContaining({ github_repo_id: 1, root_dir: null }),
    );
    expect(mockConnectRepo).toHaveBeenCalledWith(
      expect.objectContaining({ github_repo_id: 2, root_dir: null }),
    );
  });

  it("passes root_dir when a directory is entered", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));

    const input = screen.getByPlaceholderText(/e\.g\. apps\/web/i);
    fireEvent.change(input, { target: { value: "apps/web" } });

    fireEvent.click(screen.getByRole("button", { name: /connect 1 project/i }));

    await waitFor(() => {
      expect(mockConnectRepo).toHaveBeenCalledWith(
        expect.objectContaining({ root_dir: "apps/web" }),
      );
    });
  });

  it("trims whitespace from root_dir and sends null for blank input", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));

    const input = screen.getByPlaceholderText(/e\.g\. apps\/web/i);
    fireEvent.change(input, { target: { value: "  " } }); // blank after trim

    fireEvent.click(screen.getByRole("button", { name: /connect 1 project/i }));

    await waitFor(() => {
      expect(mockConnectRepo).toHaveBeenCalledWith(
        expect.objectContaining({ root_dir: null }),
      );
    });
  });

  it("shows success state after connection", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByRole("button", { name: /connect 1 project$/i }));

    await waitFor(() => {
      expect(screen.getByText(/connected successfully/i)).toBeInTheDocument();
    });
  });

  it("shows error banner on API failure during connect", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    mockConnectRepo.mockRejectedValue(new Error("API 409: already connected"));

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByRole("button", { name: /connect 1 project$/i }));

    await waitFor(() => {
      expect(screen.getByText("API 409: already connected")).toBeInTheDocument();
    });
  });

  it("shows full-page error when repo list fails to load", async () => {
    mockGetInstallationRepos.mockRejectedValue(new Error("GitHub API down"));

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => {
      expect(screen.getByText("GitHub API down")).toBeInTheDocument();
    });
  });

  // ─── Multi-directory (same repo, different subdirs) ──────────────────────────

  it("shows '+ Add another directory' button when a repo is selected", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    expect(screen.queryByText("+ Add another directory")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("org/repo1"));

    expect(screen.getByText("+ Add another directory")).toBeInTheDocument();
  });

  it("adding a directory creates a second input slot and increments project count", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));

    expect(screen.getByRole("button", { name: /connect 1 project$/i })).not.toBeDisabled();
    expect(screen.getAllByPlaceholderText(/e\.g\. apps\/web/i)).toHaveLength(1);

    fireEvent.click(screen.getByText("+ Add another directory"));

    expect(screen.getAllByPlaceholderText(/e\.g\. apps\/web/i)).toHaveLength(2);
    expect(screen.getByRole("button", { name: /connect 2 projects/i })).not.toBeDisabled();
  });

  it("remove button is hidden when there is only one slot, visible when there are multiple", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));

    // Only one slot — no remove button
    expect(screen.queryByRole("button", { name: /remove directory/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("+ Add another directory"));

    // Two slots — two remove buttons
    expect(screen.getAllByRole("button", { name: /remove directory/i })).toHaveLength(2);
  });

  it("removing a slot decrements the project count", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByText("+ Add another directory"));

    expect(screen.getByRole("button", { name: /connect 2 projects/i })).toBeInTheDocument();

    const removeButtons = screen.getAllByRole("button", { name: /remove directory/i });
    fireEvent.click(removeButtons[0]);

    expect(screen.getByRole("button", { name: /connect 1 project$/i })).toBeInTheDocument();
    expect(screen.getAllByPlaceholderText(/e\.g\. apps\/web/i)).toHaveLength(1);
  });

  it("deselecting a repo removes all its directory slots", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByText("+ Add another directory"));

    expect(screen.getAllByPlaceholderText(/e\.g\. apps\/web/i)).toHaveLength(2);

    fireEvent.click(screen.getByText("org/repo1")); // deselect

    expect(screen.queryAllByPlaceholderText(/e\.g\. apps\/web/i)).toHaveLength(0);
    expect(screen.getByRole("button", { name: /connect 0 projects/i })).toBeDisabled();
  });

  it("connects same repo twice with different root_dirs", async () => {
    mockGetInstallationRepos.mockResolvedValue([REPOS[0]]);
    mockConnectRepo.mockResolvedValue({ id: "new-id" });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/repo1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/repo1"));
    fireEvent.click(screen.getByText("+ Add another directory"));

    const inputs = screen.getAllByPlaceholderText(/e\.g\. apps\/web/i);
    fireEvent.change(inputs[0], { target: { value: "apps/web" } });
    fireEvent.change(inputs[1], { target: { value: "apps/api" } });

    fireEvent.click(screen.getByRole("button", { name: /connect 2 projects/i }));

    await waitFor(() => {
      expect(mockConnectRepo).toHaveBeenCalledTimes(2);
    });
    expect(mockConnectRepo).toHaveBeenCalledWith(
      expect.objectContaining({ github_repo_id: 1, root_dir: "apps/web" }),
    );
    expect(mockConnectRepo).toHaveBeenCalledWith(
      expect.objectContaining({ github_repo_id: 1, root_dir: "apps/api" }),
    );
  });

  // ─── Framework detection ─────────────────────────────────────────────────────

  it("shows framework badge when detection returns a result for a selected repo", async () => {
    mockGetInstallationRepos.mockResolvedValue([
      { github_repo_id: 1, full_name: "org/nextapp", name: "nextapp", default_branch: "main", private: false },
    ]);

    mockUseDetectFramework.mockReturnValue({
      result: { framework: "nextjs", language: "javascript", package_manager: "npm", confidence: 0.9 },
      isDetecting: false,
    });

    render(<RepoPicker installationId={42000} />);

    await waitFor(() => expect(screen.getByText("org/nextapp")).toBeInTheDocument());

    fireEvent.click(screen.getByText("org/nextapp"));

    await waitFor(() => {
      const img = document.querySelector("img[title]");
      expect(img).not.toBeNull();
    });
  });
});
