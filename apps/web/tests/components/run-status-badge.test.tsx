import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunStatusBadge } from "@/components/run-status-badge";

describe("RunStatusBadge", () => {
  it("renders queued status", () => {
    render(<RunStatusBadge status="queued" />);
    expect(screen.getByText("queued")).toBeDefined();
  });

  it("renders running status with pulse dot", () => {
    render(<RunStatusBadge status="running" />);
    expect(screen.getByText("running")).toBeDefined();
  });

  it("renders completed status", () => {
    render(<RunStatusBadge status="completed" />);
    expect(screen.getByText("completed")).toBeDefined();
  });

  it("renders failed status", () => {
    render(<RunStatusBadge status="failed" />);
    expect(screen.getByText("failed")).toBeDefined();
  });

  it("applies custom className", () => {
    const { container } = render(
      <RunStatusBadge status="completed" className="custom-class" />,
    );
    expect(container.firstChild?.toString()).toContain("custom");
  });
});
