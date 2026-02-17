/**
 * Tests for AgentReasoning component.
 *
 * Verifies:
 * - Component renders nothing when no traces provided
 * - Header shows model and provider
 * - Collapsible toggle opens/closes content
 * - Discovery reasoning section shown when present
 * - Patch generation reasoning section shown when present
 * - Token count displayed
 * - Null reasoning text shows fallback message
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AgentReasoning } from "@/components/agent-reasoning";
import type { ThinkingTrace } from "@/lib/types";

afterEach(() => { cleanup(); });

const baseTrace: ThinkingTrace = {
  model: "claude-sonnet-4-5",
  provider: "anthropic",
  reasoning: "Step 1: I analysed the code. Step 2: I found a regex issue.",
  prompt_tokens: 100,
  completion_tokens: 200,
  tokens_used: 300,
  timestamp: "2026-02-17T02:00:00Z",
};

describe("AgentReasoning", () => {
  it("renders nothing when both traces are null", () => {
    const { container } = render(
      <AgentReasoning discoveryTrace={null} patchTrace={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders when only discovery trace is provided", () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    expect(screen.getByText(/agent reasoning/i)).toBeDefined();
  });

  it("renders when only patch trace is provided", () => {
    render(<AgentReasoning discoveryTrace={null} patchTrace={baseTrace} />);
    expect(screen.getByText(/agent reasoning/i)).toBeDefined();
  });

  it("shows model in header", () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    expect(screen.getByText(/claude-sonnet-4-5/i)).toBeDefined();
  });

  it("shows provider label in header", () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    // Provider label includes "Claude" or "anthropic"
    expect(
      screen.getAllByText((text) =>
        text.toLowerCase().includes("claude") || text.toLowerCase().includes("anthropic")
      ).length
    ).toBeGreaterThan(0);
  });

  it("content is hidden before clicking expand", () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    expect(screen.queryByText(/Step 1: I analysed/)).toBeNull();
  });

  it("expands content on header click", async () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/Step 1: I analysed/)).toBeDefined();
    });
  });

  it("collapses content on second click", async () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.queryByText(/Step 1: I analysed/)).not.toBeNull();
    });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.queryByText(/Step 1: I analysed/)).toBeNull();
    });
  });

  it("shows discovery reasoning section title when expanded", async () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/discovery reasoning/i)).toBeDefined();
    });
  });

  it("shows patch generation reasoning section when patch trace provided", async () => {
    render(<AgentReasoning discoveryTrace={null} patchTrace={baseTrace} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/patch generation reasoning/i)).toBeDefined();
    });
  });

  it("shows both sections when both traces provided", async () => {
    const patchTrace: ThinkingTrace = { ...baseTrace, reasoning: "Patch reasoning here" };
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={patchTrace} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/discovery reasoning/i)).toBeDefined();
      expect(screen.getByText(/patch generation reasoning/i)).toBeDefined();
    });
  });

  it("shows token count when expanded", async () => {
    render(<AgentReasoning discoveryTrace={baseTrace} patchTrace={null} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      // 300 tokens total
      expect(screen.getByText(/300/)).toBeDefined();
    });
  });

  it("shows fallback when reasoning is empty", async () => {
    const emptyTrace: ThinkingTrace = { ...baseTrace, reasoning: "" };
    render(<AgentReasoning discoveryTrace={emptyTrace} patchTrace={null} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(screen.getByText(/No reasoning captured/i)).toBeDefined();
    });
  });

  it("uses custom label prop", () => {
    render(
      <AgentReasoning
        discoveryTrace={baseTrace}
        patchTrace={null}
        label="Why the agent chose this"
      />
    );
    expect(screen.getByText(/Why the agent chose this/)).toBeDefined();
  });
});
