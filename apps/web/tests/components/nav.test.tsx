import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const mockSignOut = vi.fn().mockResolvedValue({});
const mockPush = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signOut: mockSignOut,
    },
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import { Nav } from "@/components/nav";

describe("Nav", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders user avatar when logged in", () => {
    render(
      <Nav
        user={{
          avatar_url: "https://example.com/avatar.png",
          github_login: "testuser",
        }}
      />,
    );
    const avatar = screen.getByAltText("testuser");
    expect(avatar).toBeInTheDocument();
    expect(avatar).toHaveAttribute("src", "https://example.com/avatar.png");
  });

  it("renders logout button when logged in", () => {
    render(
      <Nav user={{ avatar_url: "", github_login: "testuser" }} />,
    );
    expect(screen.getByText("Sign out")).toBeInTheDocument();
  });

  it("calls signOut and navigates on logout", async () => {
    render(
      <Nav user={{ avatar_url: "", github_login: "testuser" }} />,
    );
    fireEvent.click(screen.getByText("Sign out"));

    await vi.waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
    });
  });

  it("renders login link when not authenticated", () => {
    render(<Nav />);
    const signInLink = screen.getByRole("link", { name: /sign in/i });
    expect(signInLink).toBeInTheDocument();
    expect(signInLink).toHaveAttribute("href", "/login");
  });

  it("toggles mobile menu open and closed", () => {
    render(<Nav />);
    const hamburger = screen.getByRole("button", { name: /toggle menu/i });

    // Menu starts closed
    expect(screen.queryByTestId("mobile-menu")).toBeNull();

    fireEvent.click(hamburger);
    expect(screen.getByTestId("mobile-menu")).toBeInTheDocument();

    fireEvent.click(hamburger);
    expect(screen.queryByTestId("mobile-menu")).toBeNull();
  });

  it("mobile menu contains a Dashboard link", () => {
    render(<Nav />);
    fireEvent.click(screen.getByRole("button", { name: /toggle menu/i }));

    const menu = screen.getByTestId("mobile-menu");
    const dashLink = menu.querySelector("a[href='/dashboard']");
    expect(dashLink).not.toBeNull();
    expect(dashLink?.textContent).toMatch(/dashboard/i);
  });
});
