import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockLinkInstallation = vi.fn();
const mockGet = vi.fn();
const mockPush = vi.fn();

vi.mock("@/lib/api", () => ({
  linkInstallation: (...args: unknown[]) => mockLinkInstallation(...args),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({ get: mockGet }),
  useRouter: () => ({ push: mockPush }),
}));

// Stub out RepoPicker to keep tests focused on the callback page logic
vi.mock("@/components/repo-picker", () => ({
  RepoPicker: ({ installationId }: { installationId: number }) => (
    <div data-testid="repo-picker" data-installation-id={String(installationId)} />
  ),
}));

import GitHubCallbackPage from "@/app/github/callback/page";

describe("GitHubCallbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows manual entry form when installation_id is absent", async () => {
    mockGet.mockReturnValue(null);
    render(<GitHubCallbackPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/Enter your GitHub App installation ID/i),
      ).toBeInTheDocument();
    });
  });

  it("calls linkInstallation with the parsed integer installation id", async () => {
    mockGet.mockReturnValue("999");
    mockLinkInstallation.mockResolvedValue({});
    render(<GitHubCallbackPage />);
    await waitFor(() => {
      expect(mockLinkInstallation).toHaveBeenCalledWith(999);
    });
  });

  it("shows linking state while linkInstallation is in flight", async () => {
    mockGet.mockReturnValue("42");
    mockLinkInstallation.mockImplementation(() => new Promise(() => {}));
    render(<GitHubCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText(/Linking GitHub App/i)).toBeInTheDocument();
    });
  });

  it("renders RepoPicker with the correct installationId after a successful link", async () => {
    mockGet.mockReturnValue("42");
    mockLinkInstallation.mockResolvedValue({});
    render(<GitHubCallbackPage />);
    await waitFor(() => {
      expect(screen.getByTestId("repo-picker")).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("repo-picker").getAttribute("data-installation-id"),
    ).toBe("42");
  });

  it("shows failure message when linkInstallation rejects", async () => {
    mockGet.mockReturnValue("42");
    mockLinkInstallation.mockRejectedValue(new Error("GitHub API error"));
    render(<GitHubCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to link installation/i)).toBeInTheDocument();
      expect(screen.getByText(/GitHub API error/i)).toBeInTheDocument();
    });
  });
});
