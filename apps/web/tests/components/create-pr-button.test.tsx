import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreatePRButton } from "@/components/create-pr-button";

// Mock the API module
vi.mock("@/lib/api", () => ({
  createPR: vi.fn(),
}));

import { createPR } from "@/lib/api";
const mockCreatePR = createPR as ReturnType<typeof vi.fn>;

describe("CreatePRButton", () => {
  beforeEach(() => {
    mockCreatePR.mockReset();
  });

  it("renders Create PR button by default", () => {
    render(<CreatePRButton repoId="r1" proposalId="p1" />);
    expect(screen.getByRole("button", { name: "Create PR" })).toBeDefined();
  });

  it("shows View PR link when existingPrUrl is provided", () => {
    render(
      <CreatePRButton
        repoId="r1"
        proposalId="p1"
        existingPrUrl="https://github.com/pr/1"
      />,
    );
    const link = screen.getByRole("link", { name: /View PR/i });
    expect(link.getAttribute("href")).toBe("https://github.com/pr/1");
  });

  it("shows loading state while creating PR", async () => {
    // Never resolves — keeps loading state
    mockCreatePR.mockReturnValue(new Promise(() => {}));

    render(<CreatePRButton repoId="r1" proposalId="p1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText("Creating PR…")).toBeDefined();
    });
  });

  it("shows View PR link after successful creation", async () => {
    mockCreatePR.mockResolvedValue({ pr_url: "https://github.com/pr/42" });

    render(<CreatePRButton repoId="r1" proposalId="p1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /View PR/i })).toBeDefined();
    });
  });

  it("shows error message on failure", async () => {
    mockCreatePR.mockRejectedValue(new Error("Network error"));

    render(<CreatePRButton repoId="r1" proposalId="p1" />);
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeDefined();
    });
  });

  it("button is disabled while loading", async () => {
    mockCreatePR.mockReturnValue(new Promise(() => {}));

    render(<CreatePRButton repoId="r1" proposalId="p1" />);
    const button = screen.getByRole("button");
    fireEvent.click(button);

    await waitFor(() => {
      expect(button.hasAttribute("disabled")).toBe(true);
    });
  });
});
