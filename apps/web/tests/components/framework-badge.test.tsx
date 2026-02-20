import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FrameworkBadge } from "@/components/framework-badge";

describe("FrameworkBadge", () => {
  it("renders a known framework icon with correct src and title", () => {
    render(<FrameworkBadge framework="nextjs" />);
    const img = screen.getByAltText("Next.js") as HTMLImageElement;
    expect(img).toBeDefined();
    expect(img.src).toContain("/framework-icons/nextjs.svg");
    expect(img.title).toBe("Next.js");
  });

  it("falls back to code.svg and generic label for null framework", () => {
    render(<FrameworkBadge framework={null} />);
    const img = screen.getByAltText("Unknown") as HTMLImageElement;
    expect(img.src).toContain("/framework-icons/code.svg");
    expect(img.title).toBe("Unknown");
  });

  it("falls back to code.svg for an unrecognised framework identifier", () => {
    render(<FrameworkBadge framework="totally-unknown-framework" />);
    const img = screen.getByAltText("totally-unknown-framework") as HTMLImageElement;
    expect(img.src).toContain("/framework-icons/code.svg");
  });

  it("renders the human-readable label text when showLabel is true", () => {
    render(<FrameworkBadge framework="react" showLabel />);
    expect(screen.getByText("React")).toBeDefined();
  });

  it("does not render label text when showLabel is false (default)", () => {
    render(<FrameworkBadge framework="react" />);
    expect(screen.queryByText("React")).toBeNull();
  });

  it("renders a second package manager badge when packageManager is provided", () => {
    render(<FrameworkBadge framework="nextjs" packageManager="pnpm" />);
    const imgs = screen.getAllByRole("img");
    expect(imgs.length).toBe(2);
    const pmImg = imgs[1] as HTMLImageElement;
    expect(pmImg.src).toContain("/framework-icons/pnpm.svg");
    expect(pmImg.title).toBe("pnpm");
  });

  it("does not render a package manager badge when packageManager is null", () => {
    render(<FrameworkBadge framework="nextjs" packageManager={null} />);
    const imgs = screen.getAllByRole("img");
    expect(imgs.length).toBe(1);
  });

  it("renders correct icon for react-vite framework", () => {
    render(<FrameworkBadge framework="react-vite" />);
    const img = screen.getByAltText("React + Vite") as HTMLImageElement;
    expect(img.src).toContain("/framework-icons/react.svg");
  });

  it("renders correct icon for sveltekit (maps to svelte.svg)", () => {
    render(<FrameworkBadge framework="sveltekit" />);
    const img = screen.getByAltText("SvelteKit") as HTMLImageElement;
    expect(img.src).toContain("/framework-icons/svelte.svg");
  });

  it("renders fastapi framework correctly", () => {
    render(<FrameworkBadge framework="fastapi" showLabel />);
    expect(screen.getByText("FastAPI")).toBeDefined();
    const img = screen.getByAltText("FastAPI") as HTMLImageElement;
    expect(img.src).toContain("/framework-icons/fastapi.svg");
  });
});
