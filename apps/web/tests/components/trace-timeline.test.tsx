import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TraceTimeline } from "@/components/trace-timeline";
import type { TraceAttempt } from "@/lib/types";

function makeAttempt(overrides: Partial<TraceAttempt> = {}): TraceAttempt {
  return {
    attempt_number: 1,
    patch_applied: true,
    timestamp: new Date().toISOString(),
    error: null,
    steps: [
      { name: "test", exit_code: 0, duration_seconds: 1.5, is_success: true },
    ],
    llm_reasoning: null,
    verdict: {
      is_accepted: true,
      confidence: "high",
      reason: "Tests pass and benchmark improves",
      gates_passed: ["test_gate"],
      gates_failed: [],
    },
    ...overrides,
  };
}

describe("TraceTimeline", () => {
  it("shows empty message when no attempts", () => {
    render(<TraceTimeline attempts={[]} />);
    expect(screen.getByText(/No trace data/)).toBeDefined();
  });

  it("renders attempt header", () => {
    render(<TraceTimeline attempts={[makeAttempt()]} />);
    expect(screen.getByText("Attempt 1")).toBeDefined();
  });

  it("shows Accepted label for accepted attempt", () => {
    render(<TraceTimeline attempts={[makeAttempt()]} />);
    expect(screen.getByText("Accepted")).toBeDefined();
  });

  it("shows Rejected label for rejected attempt", () => {
    render(
      <TraceTimeline
        attempts={[
          makeAttempt({
            verdict: {
              is_accepted: false,
              confidence: "low",
              reason: "Tests failed",
              gates_passed: [],
              gates_failed: ["test_gate"],
            },
          }),
        ]}
      />,
    );
    expect(screen.getByText("Rejected")).toBeDefined();
  });

  it("expands to show steps on click", () => {
    render(<TraceTimeline attempts={[makeAttempt()]} />);
    const button = screen.getByRole("button", { name: /attempt 1/i });
    fireEvent.click(button);
    expect(screen.getByText("test")).toBeDefined();
  });

  it("shows verdict reason when expanded", () => {
    render(<TraceTimeline attempts={[makeAttempt()]} />);
    const button = screen.getByRole("button", { name: /attempt 1/i });
    fireEvent.click(button);
    expect(screen.getByText("Tests pass and benchmark improves")).toBeDefined();
  });

  it("shows failed gates when expanded", () => {
    render(
      <TraceTimeline
        attempts={[
          makeAttempt({
            verdict: {
              is_accepted: false,
              confidence: "low",
              reason: "Tests failed",
              gates_passed: [],
              gates_failed: ["test_gate"],
            },
          }),
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /attempt 1/i }));
    expect(screen.getByText(/test_gate/)).toBeDefined();
  });

  it("renders multiple attempts", () => {
    render(
      <TraceTimeline
        attempts={[
          makeAttempt({ attempt_number: 1 }),
          makeAttempt({ attempt_number: 2 }),
        ]}
      />,
    );
    expect(screen.getByText("Attempt 1")).toBeDefined();
    expect(screen.getByText("Attempt 2")).toBeDefined();
  });

  it("shows error message when attempt has error", () => {
    render(
      <TraceTimeline
        attempts={[makeAttempt({ error: "Patch apply failed", verdict: null })]}
      />,
    );
    expect(screen.getByText("Patch apply failed")).toBeDefined();
  });
});
