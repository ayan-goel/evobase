import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProposalView } from "@/app/proposals/[proposalId]/page";
import type { Proposal } from "@/lib/types";

// CreatePRButton uses API — mock it to avoid network calls in page tests
vi.mock("@/lib/api", () => ({
  createPR: vi.fn(),
}));

function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "prop-1",
    run_id: "run-1",
    diff: "--- a/src/utils.ts\n+++ b/src/utils.ts\n@@ -1 +1 @@\n-old\n+new\n",
    summary: "Replaced indexOf with includes",
    metrics_before: {
      is_success: true,
      total_duration_seconds: 5.0,
      step_count: 1,
      steps: [{ name: "test", exit_code: 0, duration_seconds: 5.0, is_success: true }],
    },
    metrics_after: {
      is_success: true,
      total_duration_seconds: 4.8,
      step_count: 1,
      steps: [{ name: "test", exit_code: 0, duration_seconds: 4.8, is_success: true }],
    },
    risk_score: 0.2,
    confidence: "high",
    created_at: new Date().toISOString(),
    pr_url: null,
    artifacts: [],
    ...overrides,
  };
}

describe("ProposalView", () => {
  it("renders the proposal summary as heading", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByRole("heading", { name: "Replaced indexOf with includes" })).toBeDefined();
  });

  it("renders confidence badge", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByText("High confidence")).toBeDefined();
  });

  it("renders metrics before section", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByText("Before")).toBeDefined();
    expect(screen.getByText("After")).toBeDefined();
  });

  it("renders the diff viewer", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByRole("region", { name: /code diff/i })).toBeDefined();
  });

  it("renders Create PR button", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByRole("button", { name: "Create PR" })).toBeDefined();
  });

  it("shows View PR link when proposal has pr_url", () => {
    render(
      <ProposalView
        proposal={makeProposal({ pr_url: "https://github.com/pr/1" })}
        artifactLinks={[]}
      />,
    );
    expect(screen.getByRole("link", { name: /View PR/i })).toBeDefined();
  });

  it("renders artifact evidence links", () => {
    const artifact = {
      id: "art-1",
      proposal_id: "prop-1",
      storage_path: "repos/r/runs/r/trace.json",
      type: "trace",
      created_at: new Date().toISOString(),
    };
    render(
      <ProposalView
        proposal={makeProposal({ artifacts: [artifact] })}
        artifactLinks={[{ artifact, signedUrl: "https://storage.example.com/trace.json" }]}
      />,
    );
    expect(screen.getByText("trace.json")).toBeDefined();
  });

  it("renders fallback summary when null", () => {
    render(
      <ProposalView
        proposal={makeProposal({ summary: null })}
        artifactLinks={[]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Optimization Proposal" })).toBeDefined();
  });

  it("renders risk score", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    expect(screen.getByText(/Risk 20%/)).toBeDefined();
  });
});
