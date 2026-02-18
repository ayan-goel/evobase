import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import NotFound from "@/app/not-found";

describe("NotFound", () => {
  it("renders the not-found page", () => {
    render(<NotFound />);
    expect(screen.getByTestId("not-found")).toBeDefined();
  });

  it("shows 'Page not found' message", () => {
    render(<NotFound />);
    expect(screen.getByText(/page not found/i)).toBeDefined();
  });

  it("has a link back to the dashboard", () => {
    render(<NotFound />);
    const link = screen.getByRole("link", { name: /back to dashboard/i });
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/dashboard");
  });
});
