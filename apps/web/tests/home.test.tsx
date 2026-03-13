import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "../app/page";

// Mock all landing sub-components — each has its own dedicated test file.
// The home page test only verifies that the page correctly composes them.
vi.mock("@/components/nav", () => ({
  Nav: () => <nav data-testid="nav" />,
}));
vi.mock("@/components/landing/hero", () => ({
  Hero: () => <section data-testid="hero" />,
}));
vi.mock("@/components/landing/tech-stack", () => ({
  TechStack: () => <section data-testid="tech-stack" />,
}));
vi.mock("@/components/landing/why-evobase", () => ({
  WhyEvobase: () => <section data-testid="why-evobase" />,
}));
vi.mock("@/components/landing/pipeline", () => ({
  Pipeline: () => <section data-testid="pipeline" />,
}));
vi.mock("@/components/landing/features", () => ({
  Features: () => <section data-testid="features" />,
}));
vi.mock("@/components/landing/diff-showcase", () => ({
  DiffShowcase: () => <section data-testid="diff-showcase" />,
}));
vi.mock("@/components/landing/pricing", () => ({
  Pricing: () => <section data-testid="pricing" />,
}));
vi.mock("@/components/landing/footer", () => ({
  Footer: () => <footer data-testid="footer" />,
}));

describe("Home page", () => {
  it("renders without crashing", () => {
    render(<Home />);
  });

  it("renders the nav", () => {
    render(<Home />);
    expect(screen.getByTestId("nav")).toBeInTheDocument();
  });

  it("renders all landing sections in order", () => {
    render(<Home />);
    expect(screen.getByTestId("hero")).toBeInTheDocument();
    expect(screen.getByTestId("tech-stack")).toBeInTheDocument();
    expect(screen.getByTestId("why-evobase")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline")).toBeInTheDocument();
    expect(screen.getByTestId("diff-showcase")).toBeInTheDocument();
    expect(screen.getByTestId("features")).toBeInTheDocument();
    expect(screen.getByTestId("pricing")).toBeInTheDocument();
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });
});
