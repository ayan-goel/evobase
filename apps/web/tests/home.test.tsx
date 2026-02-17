import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "../app/page";

describe("Home page", () => {
  it("renders the heading", () => {
    render(<Home />);
    expect(screen.getByText("SelfOpt")).toBeInTheDocument();
  });

  it("renders the primary CTA button", () => {
    render(<Home />);
    expect(
      screen.getByRole("button", { name: "Get Started" })
    ).toBeInTheDocument();
  });

  it("renders the secondary CTA button", () => {
    render(<Home />);
    expect(
      screen.getByRole("button", { name: "Learn More" })
    ).toBeInTheDocument();
  });
});
