import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlanBadge } from "@/components/billing/plan-badge";

describe("PlanBadge", () => {
  it("renders the correct label for each tier", () => {
    const tiers = [
      { tier: "free", label: "Free" },
      { tier: "hobby", label: "Hobby" },
      { tier: "premium", label: "Premium" },
      { tier: "pro", label: "Pro" },
      { tier: "enterprise", label: "Enterprise" },
    ];

    for (const { tier, label } of tiers) {
      const { unmount } = render(<PlanBadge tier={tier} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("falls back gracefully for an unknown tier", () => {
    render(<PlanBadge tier="ultra-gold" />);
    // Should still render something — the raw tier string as label
    expect(screen.getByText("ultra-gold")).toBeInTheDocument();
  });

  it("applies additional className", () => {
    const { container } = render(
      <PlanBadge tier="pro" className="my-custom-class" />,
    );
    expect(container.firstChild).toHaveClass("my-custom-class");
  });

  it("is always rendered as a span", () => {
    const { container } = render(<PlanBadge tier="hobby" />);
    expect(container.querySelector("span")).toBeInTheDocument();
  });

  it("hobby tier has blue styling class", () => {
    const { container } = render(<PlanBadge tier="hobby" />);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain("blue");
  });

  it("pro tier has amber styling class", () => {
    const { container } = render(<PlanBadge tier="pro" />);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain("amber");
  });

  it("enterprise tier has emerald styling class", () => {
    const { container } = render(<PlanBadge tier="enterprise" />);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain("emerald");
  });
});
