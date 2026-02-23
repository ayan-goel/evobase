import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ValidationAttemptsPanel,
  type ValidationAttemptSummary,
} from "@/components/run-detail/validation-attempts-panel";

function makeAttempt(overrides: Partial<ValidationAttemptSummary> = {}): ValidationAttemptSummary {
  return {
    attempt_number: 1,
    patch_applied: true,
    error: null,
    timestamp: "2026-02-23T10:00:00.000Z",
    steps: [
      {
        name: "build",
        command: "npm run build",
        exit_code: 0,
        duration_seconds: 1.23,
        stdout_lines: 10,
        stderr_lines: 0,
        is_success: true,
      },
    ],
    verdict: {
      is_accepted: true,
      confidence: "high",
      reason: "All gates passed",
      gates_passed: ["test_gate"],
      gates_failed: [],
      benchmark_comparison: null,
    },
    ...overrides,
  };
}

describe("ValidationAttemptsPanel", () => {
  it("shows empty state when no attempts are provided", () => {
    render(<ValidationAttemptsPanel attempts={[]} />);
    expect(screen.getByText(/No validation attempt details captured/i)).toBeDefined();
  });

  it("renders multiple attempts", () => {
    render(
      <ValidationAttemptsPanel
        attempts={[
          makeAttempt({ attempt_number: 1 }),
          makeAttempt({ attempt_number: 2, patch_applied: false }),
        ]}
      />,
    );

    expect(screen.getByText(/Attempt 1/)).toBeDefined();
    expect(screen.getByText(/Attempt 2/)).toBeDefined();
  });

  it("renders step summaries and command details", () => {
    render(<ValidationAttemptsPanel attempts={[makeAttempt()]} />);
    expect(screen.getByText("build")).toBeDefined();
    expect(screen.getByText("exit 0")).toBeDefined();
    expect(screen.getByText("npm run build")).toBeDefined();
    expect(screen.getByText(/10 stdout lines · 0 stderr lines/)).toBeDefined();
  });

  it("renders attempt error when present", () => {
    render(
      <ValidationAttemptsPanel
        attempts={[makeAttempt({ patch_applied: false, error: "Patch apply failed" })]}
      />,
    );
    expect(screen.getByText(/Patch apply failed/)).toBeDefined();
  });
});
