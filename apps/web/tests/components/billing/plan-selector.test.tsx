import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { PlanSelector } from "@/components/billing/plan-selector";

describe("PlanSelector", () => {
  const onSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a button for every plan option", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} />);
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("Hobby")).toBeInTheDocument();
    expect(screen.getByText("Premium")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
  });

  it("shows price labels on paid tiers", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} />);
    expect(screen.getByText("$20/mo")).toBeInTheDocument();
    expect(screen.getByText("$60/mo")).toBeInTheDocument();
    expect(screen.getByText("$200/mo")).toBeInTheDocument();
  });

  it("marks the current tier as (current)", () => {
    render(<PlanSelector currentTier="hobby" onSelect={onSelect} />);
    expect(screen.getByText("(current)")).toBeInTheDocument();
  });

  it("calls onSelect with the correct tier on click", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Hobby"));
    expect(onSelect).toHaveBeenCalledWith("hobby");
  });

  it("does not call onSelect when clicking the current tier button", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} />);
    const freeButton = screen.getByText("Free").closest("button")!;
    expect(freeButton).toBeDisabled();
    fireEvent.click(freeButton);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("disables all buttons when disabled=true", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} disabled />);
    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn).toBeDisabled();
    }
  });

  it("does not call onSelect when globally disabled", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} disabled />);
    fireEvent.click(screen.getByText("Premium"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("shows no price label for the free tier", () => {
    render(<PlanSelector currentTier="pro" onSelect={onSelect} />);
    const freeButton = screen.getByText("Free").closest("button")!;
    expect(freeButton.textContent).not.toContain("$");
  });

  it("renders correctly when currentTier is pro", () => {
    render(<PlanSelector currentTier="pro" onSelect={onSelect} />);
    // All non-current buttons should be enabled
    const buttons = screen.getAllByRole("button");
    const proButton = buttons.find((b) => b.textContent?.includes("Pro") && b.textContent?.includes("current"))!;
    expect(proButton).toBeDisabled();

    const hobbyButton = buttons.find((b) => b.textContent?.includes("Hobby"))!;
    expect(hobbyButton).not.toBeDisabled();
  });

  it("onSelect fires once per click", () => {
    render(<PlanSelector currentTier="free" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Pro"));
    fireEvent.click(screen.getByText("Pro"));
    expect(onSelect).toHaveBeenCalledTimes(2);
    expect(onSelect).toHaveBeenCalledWith("pro");
  });
});
