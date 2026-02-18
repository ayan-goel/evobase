import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithOAuth: vi.fn(),
    },
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  it("renders sign in with GitHub button", () => {
    render(<LoginPage />);
    const button = screen.getByRole("button", {
      name: /sign in with github/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("renders app branding", () => {
    render(<LoginPage />);
    expect(screen.getByText("Coreloop")).toBeInTheDocument();
  });

  it("does not show authenticated content", () => {
    render(<LoginPage />);
    expect(screen.queryByText(/dashboard/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sign out/i)).not.toBeInTheDocument();
  });
});
