import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProposalCard } from "@/components/proposal-card";
import type { Proposal } from "@/lib/types";

function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "proposal-1",
    run_id: "run-1",
    repo_id: "repo-1",
    diff: "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n",
    summary: "Replaced indexOf with includes",
    metrics_before: null,
    metrics_after: null,
    risk_score: 0.2,
    confidence: "high",
    created_at: new Date().toISOString(),
    pr_url: null,
    framework: null,
    patch_variants: [],
    selection_reason: null,
    approaches_tried: null,
    artifacts: [],
    discovery_trace: null,
    patch_trace: null,
    ...overrides,
  };
}

describe("ProposalCard", () => {
  it("renders the summary", () => {
    render(<ProposalCard proposal={makeProposal()} />);
    expect(screen.getByText("Replaced indexOf with includes")).toBeDefined();
  });

  it("fires onSelect when clicked", () => {
    const onSelect = vi.fn();
    render(<ProposalCard proposal={makeProposal()} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("does not throw when onSelect is not provided", () => {
    render(<ProposalCard proposal={makeProposal()} />);
    expect(() => fireEvent.click(screen.getByRole("button"))).not.toThrow();
  });

  it("renders fallback summary when null", () => {
    render(<ProposalCard proposal={makeProposal({ summary: null })} />);
    expect(screen.getByText("Optimization proposal")).toBeDefined();
  });

  it("shows PR created label when pr_url exists", () => {
    render(
      <ProposalCard
        proposal={makeProposal({ pr_url: "https://github.com/pr/1" })}
      />,
    );
    expect(screen.getByText("PR created")).toBeDefined();
  });

  it("shows View arrow when no PR yet", () => {
    render(<ProposalCard proposal={makeProposal({ pr_url: null })} />);
    expect(screen.getByText("View →")).toBeDefined();
  });

  it("renders metrics delta when metrics available", () => {
    const proposal = makeProposal({
      metrics_before: {
        is_success: true,
        total_duration_seconds: 5.0,
        step_count: 1,
        steps: [{ name: "test", exit_code: 0, duration_seconds: 5.0, is_success: true }],
      } as Proposal["metrics_before"],
      metrics_after: {
        is_success: true,
        total_duration_seconds: 4.5,
        step_count: 1,
        steps: [{ name: "test", exit_code: 0, duration_seconds: 4.5, is_success: true }],
      } as Proposal["metrics_after"],
    });
    render(<ProposalCard proposal={proposal} />);
    // Should show some test time metric
    expect(screen.getByText(/Test time/)).toBeDefined();
  });

  it("renders as a button (not a link)", () => {
    render(<ProposalCard proposal={makeProposal({ id: "abc-123" })} />);
    expect(screen.getByRole("button")).toBeDefined();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
