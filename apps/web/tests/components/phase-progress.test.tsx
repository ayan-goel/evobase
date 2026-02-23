import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PhaseProgress } from "@/components/run-detail/phase-progress";

describe("PhaseProgress", () => {
  it("renders all phase labels", () => {
    render(<PhaseProgress currentPhase={null} isDone={false} />);
    expect(screen.getByText("Clone")).toBeDefined();
    expect(screen.getByText("Detect")).toBeDefined();
    expect(screen.getByText("Baseline")).toBeDefined();
    expect(screen.getByText("Discover")).toBeDefined();
    expect(screen.getByText("Validate")).toBeDefined();
    expect(screen.getByText("Done")).toBeDefined();
  });

  it("marks all phases complete when isDone is true", () => {
    const { container } = render(
      <PhaseProgress currentPhase="run" isDone={true} />,
    );
    const bars = container.querySelectorAll(".bg-emerald-500\\/70");
    expect(bars.length).toBe(6);
  });

  it("shows no active phase when currentPhase is null", () => {
    const { container } = render(
      <PhaseProgress currentPhase={null} isDone={false} />,
    );
    const activeBars = container.querySelectorAll(".bg-blue-500\\/70");
    expect(activeBars.length).toBe(0);
  });
});
