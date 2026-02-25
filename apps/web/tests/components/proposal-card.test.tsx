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

  it("renders changed file name and +/- counts from diff", () => {
    const proposal = makeProposal({
      diff: "--- a/src/utils.ts\n+++ b/src/utils.ts\n@@ -1,4 +1,5 @@\n context\n-old line\n+new line 1\n+new line 2\n context\n",
    });
    render(<ProposalCard proposal={proposal} />);
    expect(screen.getByText("src/utils.ts")).toBeDefined();
    expect(screen.getByText("+2")).toBeDefined();
    expect(screen.getByText("−1")).toBeDefined();
  });

  it("shows only last two path segments for deep paths", () => {
    const proposal = makeProposal({
      diff: "--- a/apps/web/components/Foo.tsx\n+++ b/apps/web/components/Foo.tsx\n@@ -1 +1 @@\n-x\n+y\n",
    });
    render(<ProposalCard proposal={proposal} />);
    expect(screen.getByText("components/Foo.tsx")).toBeDefined();
  });

  it("shows overflow indicator when more than 3 files changed", () => {
    const files = ["a.ts", "b.ts", "c.ts", "d.ts"];
    const diff = files
      .map((f) => `--- a/${f}\n+++ b/${f}\n@@ -1 +1 @@\n-x\n+y\n`)
      .join("");
    const proposal = makeProposal({ diff });
    render(<ProposalCard proposal={proposal} />);
    expect(screen.getByText("+1 more file")).toBeDefined();
  });

  it("shows nothing when diff is empty", () => {
    const proposal = makeProposal({ diff: "" });
    render(<ProposalCard proposal={proposal} />);
    // No file rows rendered — just summary and footer
    expect(screen.queryByText(/more file/)).toBeNull();
  });

  it("renders as a button (not a link)", () => {
    render(<ProposalCard proposal={makeProposal({ id: "abc-123" })} />);
    expect(screen.getByRole("button")).toBeDefined();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
