import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "../app/page";

describe("Home page", () => {
  it("renders the heading", () => {
    render(<Home />);
    expect(screen.getByText("Coreloop")).toBeInTheDocument();
  });

  it("renders the primary CTA link to login", () => {
    render(<Home />);
    const link = screen.getByRole("link", { name: "Get Started" });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toBe("/login");
  });

  it("renders the secondary CTA link to GitHub", () => {
    render(<Home />);
    const link = screen.getByRole("link", { name: "View on GitHub" });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toContain("github.com");
  });
});
