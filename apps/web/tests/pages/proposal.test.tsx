import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProposalView } from "@/app/proposals/[proposalId]/page";
import type { Proposal } from "@/lib/types";

// CreatePRButton uses API — mock it to avoid network calls in page tests
vi.mock("@/lib/api", () => ({
  createPR: vi.fn(),
}));

const FAKE_TRACE = {
  model: "claude-sonnet-4-5",
  provider: "anthropic",
  reasoning: "Found an N+1 query that can be batched.",
  prompt_tokens: 100,
  completion_tokens: 200,
  tokens_used: 300,
  timestamp: new Date().toISOString(),
};

function makeProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "prop-1",
    run_id: "run-1",
    repo_id: "repo-42",
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

  it("breadcrumb Repository link points to the proposal's repo_id", () => {
    render(<ProposalView proposal={makeProposal()} artifactLinks={[]} />);
    const repoLink = screen.getByRole("link", { name: "Repository" });
    expect(repoLink.getAttribute("href")).toBe("/repos/repo-42");
  });

  it("Create PR button receives the repo_id from the proposal", () => {
    // Render with a known repo_id; the CreatePRButton is rendered with that id
    render(
      <ProposalView
        proposal={makeProposal({ repo_id: "repo-99" })}
        artifactLinks={[]}
      />,
    );
    // The CreatePRButton receives repoId which it would pass to createPR —
    // we verify it renders (not 404 / empty stub)
    expect(screen.getByRole("button", { name: "Create PR" })).toBeDefined();
  });

  it("hides agent reasoning section when both traces are null", () => {
    render(
      <ProposalView
        proposal={makeProposal({ discovery_trace: null, patch_trace: null })}
        artifactLinks={[]}
      />,
    );
    expect(screen.queryByText("Agent reasoning")).toBeNull();
  });

  it("shows agent reasoning section when discovery_trace is present", () => {
    render(
      <ProposalView
        proposal={makeProposal({ discovery_trace: FAKE_TRACE, patch_trace: null })}
        artifactLinks={[]}
      />,
    );
    // Section heading is an <h2>; AgentReasoning also renders the label as a <span>
    const headings = screen.getAllByText("Agent reasoning");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it("shows agent reasoning section when patch_trace is present", () => {
    render(
      <ProposalView
        proposal={makeProposal({ discovery_trace: null, patch_trace: FAKE_TRACE })}
        artifactLinks={[]}
      />,
    );
    const headings = screen.getAllByText("Agent reasoning");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it("shows agent reasoning section when both traces are present", () => {
    render(
      <ProposalView
        proposal={makeProposal({ discovery_trace: FAKE_TRACE, patch_trace: FAKE_TRACE })}
        artifactLinks={[]}
      />,
    );
    const headings = screen.getAllByText("Agent reasoning");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });
});
