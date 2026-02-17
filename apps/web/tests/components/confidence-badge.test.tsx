import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceBadge } from "@/components/confidence-badge";

describe("ConfidenceBadge", () => {
  it("renders high confidence", () => {
    render(<ConfidenceBadge confidence="high" />);
    expect(screen.getByText("High confidence")).toBeDefined();
  });

  it("renders medium confidence", () => {
    render(<ConfidenceBadge confidence="medium" />);
    expect(screen.getByText("Medium confidence")).toBeDefined();
  });

  it("renders low confidence with review note", () => {
    render(<ConfidenceBadge confidence="low" />);
    expect(screen.getByText("Low confidence — review required")).toBeDefined();
  });

  it("renders nothing when confidence is null", () => {
    const { container } = render(<ConfidenceBadge confidence={null} />);
    expect(container.firstChild).toBeNull();
  });
});
