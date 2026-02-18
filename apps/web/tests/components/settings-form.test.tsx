/**
 * Tests for SettingsForm component.
 *
 * Verifies:
 * - All fields render with initial values
 * - Paused warning banner shown when paused
 * - Unpause button calls API with paused: false
 * - Save button calls updateRepoSettings with form values
 * - Saved confirmation shown after success
 * - Error message shown on API failure
 * - Failure counters rendered when non-zero
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsForm } from "@/components/settings-form";
import type { Repository, RepoSettings } from "@/lib/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api", () => ({
  updateRepoSettings: vi.fn(),
}));

import { updateRepoSettings } from "@/lib/api";

const mockUpdateRepoSettings = vi.mocked(updateRepoSettings);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseSettings: RepoSettings = {
  repo_id: "repo-1",
  compute_budget_minutes: 60,
  max_proposals_per_run: 10,
  max_candidates_per_run: 20,
  schedule: "0 2 * * *",
  paused: false,
  consecutive_setup_failures: 0,
  consecutive_flaky_runs: 0,
  last_run_at: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SettingsForm", () => {
  it("renders schedule input with initial value", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    const input = screen.getByPlaceholderText("0 2 * * *") as HTMLInputElement;
    expect(input.value).toBe("0 2 * * *");
  });

  it("renders compute budget input", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.getByDisplayValue("60")).toBeDefined();
  });

  it("renders max proposals input", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.getByDisplayValue("10")).toBeDefined();
  });

  it("renders max candidates input", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.getByDisplayValue("20")).toBeDefined();
  });

  it("renders save button", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.getByRole("button", { name: /save settings/i })).toBeDefined();
  });

  it("does not show paused warning when not paused", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.queryByText(/scheduled runs are paused/i)).toBeNull();
  });

  it("shows paused warning when paused", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, paused: true }}
      />
    );
    expect(screen.getByText(/scheduled runs are paused/i)).toBeDefined();
  });

  it("shows unpause button when paused", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, paused: true }}
      />
    );
    expect(screen.getByRole("button", { name: /unpause/i })).toBeDefined();
  });

  it("shows setup failure message when consecutive_setup_failures >= 3", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, paused: true, consecutive_setup_failures: 3 }}
      />
    );
    expect(screen.getByText(/Setup failed 3/i)).toBeDefined();
  });

  it("shows flaky run message when consecutive_flaky_runs >= 5", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, paused: true, consecutive_flaky_runs: 5 }}
      />
    );
    expect(screen.getByText(/Tests were flaky for 5/i)).toBeDefined();
  });

  it("shows failure counter section when counters are non-zero", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, consecutive_setup_failures: 2 }}
      />
    );
    expect(screen.getByText(/setup failures/i)).toBeDefined();
  });

  it("does not show counter section when counters are zero", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.queryByText(/setup failures/i)).toBeNull();
  });

  it("calls updateRepoSettings on save", async () => {
    mockUpdateRepoSettings.mockResolvedValueOnce(baseSettings);
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);

    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(mockUpdateRepoSettings).toHaveBeenCalledWith(
        "repo-1",
        expect.objectContaining({ compute_budget_minutes: 60 })
      );
    });
  });

  it("shows saved confirmation after successful save", async () => {
    mockUpdateRepoSettings.mockResolvedValueOnce(baseSettings);
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);

    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByText(/settings saved/i)).toBeDefined();
    });
  });

  it("shows error message when save fails", async () => {
    mockUpdateRepoSettings.mockRejectedValueOnce(new Error("Server error"));
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);

    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() => {
      expect(screen.getByText(/Server error/i)).toBeDefined();
    });
  });

  it("calls updateRepoSettings with paused: false on unpause", async () => {
    mockUpdateRepoSettings.mockResolvedValueOnce({ ...baseSettings, paused: false });
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, paused: true }}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /unpause/i }));

    await waitFor(() => {
      expect(mockUpdateRepoSettings).toHaveBeenCalledWith("repo-1", { paused: false });
    });
  });

  it("renders last_run_at when present", () => {
    render(
      <SettingsForm
        repoId="repo-1"
        initial={{ ...baseSettings, last_run_at: "2026-02-17T02:00:00Z" }}
      />
    );
    expect(screen.getByText(/last scheduled run/i)).toBeDefined();
  });

  it("does not render last_run_at section when null", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} />);
    expect(screen.queryByText(/last scheduled run/i)).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // Detected commands
  // ---------------------------------------------------------------------------

  const baseRepo: Repository = {
    id: "repo-1",
    github_repo_id: null,
    github_full_name: "acme/api",
    default_branch: "main",
    installation_id: null,
    package_manager: "npm",
    install_cmd: "npm ci",
    build_cmd: "npm run build",
    test_cmd: "npm test",
    typecheck_cmd: null,
    latest_run_status: null,
    created_at: new Date().toISOString(),
  };

  it("renders detected commands section when repo has commands", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} repo={baseRepo} />);
    expect(screen.getByTestId("detected-commands")).toBeDefined();
    expect(screen.getByDisplayValue("npm ci")).toBeDefined();
    expect(screen.getByDisplayValue("npm run build")).toBeDefined();
    expect(screen.getByDisplayValue("npm test")).toBeDefined();
  });

  it("detected command inputs are read-only", () => {
    render(<SettingsForm repoId="repo-1" initial={baseSettings} repo={baseRepo} />);
    const installInput = screen.getByDisplayValue("npm ci") as HTMLInputElement;
    expect(installInput.readOnly).toBe(true);
  });

  it("hides detected commands section when all command fields are null", () => {
    const repoNoCommands: Repository = {
      ...baseRepo,
      install_cmd: null,
      build_cmd: null,
      test_cmd: null,
      typecheck_cmd: null,
    };
    render(<SettingsForm repoId="repo-1" initial={baseSettings} repo={repoNoCommands} />);
    expect(screen.queryByTestId("detected-commands")).toBeNull();
  });
});
