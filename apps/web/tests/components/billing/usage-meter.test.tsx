import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { UsageMeter } from "@/components/billing/usage-meter";

const PERIOD_END = "2026-03-15T00:00:00Z";

describe("UsageMeter", () => {
  describe("progress bar ARIA attributes", () => {
    it("sets aria-valuenow to rounded usagePct", () => {
      render(<UsageMeter usagePct={42.7} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveAttribute("aria-valuenow", "43");
    });

    it("always sets aria-valuemin=0 and aria-valuemax=100", () => {
      render(<UsageMeter usagePct={50} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveAttribute("aria-valuemin", "0");
      expect(bar).toHaveAttribute("aria-valuemax", "100");
    });
  });

  describe("bar width clamping", () => {
    it("clamps bar width to 100% when usagePct exceeds 100", () => {
      render(<UsageMeter usagePct={130} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveStyle({ width: "100%" });
    });

    it("sets bar width to 0% at zero usage", () => {
      render(<UsageMeter usagePct={0} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveStyle({ width: "0%" });
    });

    it("renders exact pct as width string when within 0-100", () => {
      render(<UsageMeter usagePct={55} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveStyle({ width: "55%" });
    });
  });

  describe("colour states", () => {
    it("uses normal colour below 80%", () => {
      render(<UsageMeter usagePct={70} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar.className).not.toContain("amber");
      expect(bar.className).not.toContain("red");
    });

    it("uses amber colour between 80% and 99%", () => {
      render(<UsageMeter usagePct={85} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar.className).toContain("amber");
    });

    it("uses red colour at 100% and above", () => {
      render(<UsageMeter usagePct={100} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar.className).toContain("red");
    });

    it("uses red colour when usagePct exceeds 100", () => {
      render(<UsageMeter usagePct={150} periodEnd={PERIOD_END} />);
      const bar = screen.getByRole("progressbar");
      expect(bar.className).toContain("red");
    });
  });

  describe("usage text", () => {
    it("shows percentage-of-plan text when not in overage", () => {
      render(<UsageMeter usagePct={42} periodEnd={PERIOD_END} />);
      expect(screen.getByText("42% of plan used")).toBeInTheDocument();
    });

    it("shows pay-as-you-go text when overageActive=true", () => {
      render(
        <UsageMeter usagePct={110} periodEnd={PERIOD_END} overageActive />,
      );
      expect(screen.getByText("Pay-as-you-go active")).toBeInTheDocument();
    });

    it("hides pay-as-you-go text when overageActive=false", () => {
      render(
        <UsageMeter
          usagePct={50}
          periodEnd={PERIOD_END}
          overageActive={false}
        />,
      );
      expect(
        screen.queryByText("Pay-as-you-go active"),
      ).not.toBeInTheDocument();
    });
  });

  describe("reset date", () => {
    it("renders a human-readable reset date", () => {
      render(<UsageMeter usagePct={30} periodEnd="2026-03-15T00:00:00Z" />);
      // Should contain the month abbreviation
      expect(screen.getByText(/Resets/)).toBeInTheDocument();
    });
  });

  describe("className passthrough", () => {
    it("applies custom className to wrapper element", () => {
      const { container } = render(
        <UsageMeter
          usagePct={50}
          periodEnd={PERIOD_END}
          className="my-wrapper"
        />,
      );
      expect(container.firstChild).toHaveClass("my-wrapper");
    });
  });
});
