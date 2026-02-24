import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EventCard } from "@/components/run-detail/event-card";
import type { RunEvent } from "@/lib/types";

function makeEvent(overrides: Partial<RunEvent>): RunEvent {
  return {
    id: "1-0",
    type: "clone.started",
    phase: "clone",
    ts: "2026-02-23T03:14:24.000Z",
    data: {},
    ...overrides,
  } as RunEvent;
}

describe("EventCard", () => {
  it("renders clone.started event", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "clone.started",
          phase: "clone",
          data: { repo: "org/repo" },
        })}
      />,
    );
    expect(screen.getByText(/org\/repo/)).toBeDefined();
  });

  it("renders clone.completed with sha", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "clone.completed",
          phase: "clone",
          data: { sha: "abc1234", commit_message: "fix things" },
        })}
      />,
    );
    expect(screen.getByText("abc1234")).toBeDefined();
    expect(screen.getByText(/fix things/)).toBeDefined();
  });

  it("renders detection.completed with language and framework", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "detection.completed",
          phase: "detection",
          data: {
            language: "javascript",
            framework: "nextjs",
            package_manager: "npm",
            confidence: 0.85,
          },
        })}
      />,
    );
    expect(screen.getByText("javascript")).toBeDefined();
    expect(screen.getByText("nextjs")).toBeDefined();
  });

  it("renders expandable discovery.file.analysed row with opportunities", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "discovery.file.analysed",
          phase: "discovery",
          data: {
            file: "components/settings-form.tsx",
            file_index: 2,
            total_files: 10,
            opportunities_found: 1,
            opportunities: [
              {
                file: "components/settings-form.tsx",
                location: "components/settings-form.tsx:42",
                type: "performance",
                rationale: "Derived values are recalculated on every render.",
                risk_level: "low",
                affected_lines: 4,
                approaches: ["Cache derived values after input normalization."],
              },
            ],
          },
        })}
      />,
    );

    const summaryButton = screen.getByRole("button", { name: /1 opportunity found/i });
    expect(summaryButton).toBeDefined();
    expect(screen.getByText(/1 opportunity found/i)).toBeDefined();
    expect(screen.queryByText(/Derived values are recalculated/)).toBeNull();

    fireEvent.click(summaryButton);

    expect(screen.getByText("performance")).toBeDefined();
    expect(screen.getByText(/Derived values are recalculated/)).toBeDefined();
    expect(screen.getByText(/Cache derived values after input normalization/)).toBeDefined();
    expect(screen.getByText(/risk: low/i)).toBeDefined();
    expect(screen.getByText(/4 lines/i)).toBeDefined();
    expect(screen.getByTitle("components/settings-form.tsx")).toBeDefined();
    expect(screen.getByTitle("components/settings-form.tsx:42")).toBeDefined();
  });

  it("renders non-expandable discovery.file.analysed row when no opportunities are found", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "discovery.file.analysed",
          phase: "discovery",
          data: {
            file: "components/empty.tsx",
            file_index: 0,
            total_files: 1,
            opportunities_found: 0,
            opportunities: [],
          },
        })}
      />,
    );

    expect(screen.getByText(/nothing to improve/i)).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("falls back to count-only discovery.file.analysed row for older payloads", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "discovery.file.analysed",
          phase: "discovery",
          data: {
            file: "components/legacy.tsx",
            file_index: 0,
            total_files: 1,
            opportunities_found: 2,
          },
        })}
      />,
    );

    expect(screen.getByText(/2 opportunities found/i)).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renders backtick code spans in rationale as <code> elements", () => {
    const { container } = render(
      <EventCard
        event={makeEvent({
          type: "discovery.file.analysed",
          phase: "discovery",
          data: {
            file: "components/foo.tsx",
            file_index: 0,
            total_files: 1,
            opportunities_found: 1,
            opportunities: [
              {
                file: "components/foo.tsx",
                location: "components/foo.tsx:10",
                type: "performance",
                rationale: "The `useMemo` hook is missing here.",
                risk_level: "low",
                affected_lines: 2,
                approaches: [
                  "Wrap with `React.memo` to prevent re-renders.",
                ],
              },
            ],
          },
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /1 opportunity found/i }));

    const codeElements = container.querySelectorAll("code");
    const codeTexts = Array.from(codeElements).map((el) => el.textContent);
    expect(codeTexts).toContain("useMemo");
    expect(codeTexts).toContain("React.memo");
  });

  it("renders discovery.file.analysing as a blue card with analysing badge", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "discovery.file.analysing",
          phase: "discovery",
          data: {
            file: "components/run-detail/event-card.tsx",
            file_index: 0,
            total_files: 5,
          },
        })}
      />,
    );

    expect(screen.getByText(/event-card\.tsx/i)).toBeDefined();
    expect(screen.getByText(/analysing…/i)).toBeDefined();
    expect(screen.getByText("1/5")).toBeDefined();
  });

  it("renders expandable patch.approach.started row with enriched detail", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "patch.approach.started",
          phase: "patching",
          data: {
            location: "components/run-detail/event-card.tsx:225",
            type: "performance",
            approach_index: 0,
            total_approaches: 2,
            approach_desc: "Memoize expensive timeline item grouping.",
            approach_desc_full:
              "Memoize expensive timeline item grouping and avoid recomputing the grouped structure unless the event list changes.",
            rationale:
              "The grouped timeline items are rebuilt on every render, causing avoidable work while the event stream updates.",
            risk_level: "low",
            affected_lines: 12,
          },
        })}
      />,
    );

    const rowButton = screen.getByRole("button", { name: /Generating approach/i });
    expect(rowButton).toBeDefined();
    fireEvent.click(rowButton);

    expect(screen.getByText(/Full approach/i)).toBeDefined();
    expect(screen.getByText(/grouped timeline items are rebuilt/i)).toBeDefined();
    expect(screen.getByText(/risk: low/i)).toBeDefined();
    expect(screen.getByText(/12 affected lines/i)).toBeDefined();
    expect(screen.getAllByTitle("components/run-detail/event-card.tsx:225").length).toBeGreaterThan(0);
  });

  it("renders expandable patch.approach.completed success row with trace and diff", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "patch.approach.completed",
          phase: "patching",
          data: {
            success: true,
            approach_index: 0,
            lines_changed: 8,
            touched_files: ["components/run-detail/event-card.tsx"],
            location: "components/run-detail/event-card.tsx:225",
            type: "performance",
            total_approaches: 2,
            approach_desc_full: "Memoize grouped timeline items.",
            explanation: "Memoizes grouped rows to avoid repeated timeline regrouping.",
            diff: "--- a/components/run-detail/event-card.tsx\n+++ b/components/run-detail/event-card.tsx\n@@ -1 +1 @@\n-a\n+b\n",
            patch_trace: {
              model: "claude-sonnet-4-5",
              provider: "anthropic",
              reasoning: "I memoized the grouped event rows to reduce recomputation.",
              prompt_tokens: 100,
              completion_tokens: 80,
              tokens_used: 180,
              timestamp: "2026-02-23T10:00:00.000Z",
            },
            failure_stage: null,
            failure_reason: null,
            patchgen_tries: [
              {
                attempt_number: 1,
                success: true,
                failure_stage: null,
                failure_reason: null,
                diff: "--- a/components/run-detail/event-card.tsx\n+++ b/components/run-detail/event-card.tsx\n@@ -1 +1 @@\n-a\n+b\n",
                explanation: "Memoizes grouped rows",
                touched_files: ["components/run-detail/event-card.tsx"],
                estimated_lines_changed: 8,
                patch_trace: {
                  model: "claude-sonnet-4-5",
                  provider: "anthropic",
                  reasoning: "Try 1 reasoning",
                  prompt_tokens: 10,
                  completion_tokens: 20,
                  tokens_used: 30,
                  timestamp: "2026-02-23T10:00:00.000Z",
                },
              },
            ],
          },
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Patch ready/i }));

    // Explanation and diff are shown inline (no collapsible needed)
    expect(screen.getByText(/Patch explanation/i)).toBeDefined();
    expect(screen.getByText(/Memoizes grouped rows to avoid repeated timeline regrouping/i)).toBeDefined();
    expect(screen.getByText(/--- a\/components\/run-detail\/event-card\.tsx/)).toBeDefined();

    // Patch generation tries section has been removed
    expect(screen.queryByText(/Patch generation tries/i)).toBeNull();

    // Reasoning is still available as a collapsible
    fireEvent.click(screen.getByRole("button", { name: /Patch generation reasoning/i }));
    expect(screen.getByText(/memoized the grouped event rows/i)).toBeDefined();
  });

  it("renders expandable patch.approach.completed failure row with diagnostics", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "patch.approach.completed",
          phase: "patching",
          data: {
            success: false,
            approach_index: 1,
            lines_changed: null,
            touched_files: [],
            location: "components/run-detail/run-detail-view.tsx:267",
            type: "performance",
            total_approaches: 2,
            approach_desc_full: "Wrap GroupedTimeline with React.memo.",
            explanation: null,
            diff: null,
            patch_trace: {
              model: "claude-sonnet-4-5",
              provider: "anthropic",
              reasoning: "I attempted a memoization refactor.",
              prompt_tokens: 12,
              completion_tokens: 22,
              tokens_used: 34,
              timestamp: "2026-02-23T10:00:00.000Z",
            },
            failure_stage: "json_parse",
            failure_reason: "Expecting value: line 1 column 1 (char 0)",
            patchgen_tries: [
              {
                attempt_number: 1,
                success: false,
                failure_stage: "json_parse",
                failure_reason: "Expecting value: line 1 column 1 (char 0)",
                diff: null,
                explanation: null,
                touched_files: [],
                estimated_lines_changed: 0,
                patch_trace: {
                  model: "claude-sonnet-4-5",
                  provider: "anthropic",
                  reasoning: "Try 1 parse-failure reasoning",
                  prompt_tokens: 12,
                  completion_tokens: 22,
                  tokens_used: 34,
                  timestamp: "2026-02-23T10:00:00.000Z",
                },
              },
            ],
          },
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Approach 2 failed/i }));
    expect(screen.getByText(/Failure stage: json_parse/i)).toBeDefined();
    expect(screen.getAllByText(/Expecting value: line 1 column 1/i).length).toBeGreaterThan(0);
    // Patch generation tries section has been removed — "Try 1" no longer rendered
    expect(screen.queryByText(/Try 1/)).toBeNull();
  });

  it("falls back to compact patch rows for older patch payloads", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "patch.approach.completed",
          phase: "patching",
          data: {
            success: false,
            approach_index: 0,
            touched_files: [],
          },
        })}
      />,
    );

    expect(screen.getByText(/Approach 1 failed/i)).toBeDefined();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renders validation verdict with benchmark and attempts details", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "validation.verdict",
          phase: "validation",
          data: {
            opportunity: "components/run-detail/event-card.tsx:225",
            accepted: false,
            confidence: "low",
            reason: "Patch generation failed, so validation did not run.",
            gates_passed: [],
            gates_failed: ["exception"],
            approaches_tried: 2,
            benchmark_comparison: {
              improvement_pct: -1.5,
              passes_threshold: false,
              is_significant: true,
              baseline_duration_seconds: 1.0,
              candidate_duration_seconds: 1.015,
            },
            attempts: [
              {
                attempt_number: 1,
                patch_applied: false,
                error: "Patch apply error: malformed diff",
                timestamp: "2026-02-23T10:00:00.000Z",
                steps: [
                  {
                    name: "build",
                    command: "npm run build",
                    exit_code: 0,
                    duration_seconds: 1.23,
                    stdout_lines: 4,
                    stderr_lines: 0,
                    is_success: true,
                  },
                ],
                verdict: {
                  is_accepted: false,
                  confidence: "low",
                  reason: "Exception gate failed",
                  gates_passed: [],
                  gates_failed: ["exception"],
                  benchmark_comparison: null,
                },
              },
            ],
          },
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /rejected/i }));
    expect(screen.getByText(/Benchmark comparison/i)).toBeDefined();
    expect(screen.getByText(/-1\.5% vs baseline/i)).toBeDefined();
    expect(screen.getByText(/Validation attempts \(1\)/i)).toBeDefined();
    expect(screen.getByText(/Attempt 1/)).toBeDefined();
    expect(screen.getByText(/npm run build/)).toBeDefined();
    expect(screen.getByText(/4 stdout lines · 0 stderr lines/)).toBeDefined();
  });

  it("renders baseline.step.completed success", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "baseline.step.completed",
          phase: "baseline",
          data: {
            step: "install",
            exit_code: 0,
            duration: 34.7,
            success: true,
            command: "npm ci",
          },
        })}
      />,
    );
    expect(screen.getByText("install")).toBeDefined();
    expect(screen.getByText("OK")).toBeDefined();
  });

  it("renders baseline.step.completed failure", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "baseline.step.completed",
          phase: "baseline",
          data: {
            step: "test",
            exit_code: 1,
            duration: 8.0,
            success: false,
            stderr_tail: "FAIL src/app.test.ts",
            command: "npm test",
          },
        })}
      />,
    );
    expect(screen.getByText("test")).toBeDefined();
    expect(screen.getByText(/FAILED/)).toBeDefined();
  });

  it("renders run.completed event", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "run.completed",
          phase: "run",
          data: {
            proposals_created: 3,
            candidates_attempted: 5,
            accepted: 3,
          },
        })}
      />,
    );
    expect(screen.getByText(/3 proposals created/)).toBeDefined();
  });

  it("renders run.failed event", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "run.failed",
          phase: "run",
          data: { reason: "baseline_failed", failure_step: "test" },
        })}
      />,
    );
    expect(screen.getByText("Run failed")).toBeDefined();
  });

  it("renders run.cancelled event", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "run.cancelled",
          phase: "run",
          data: {},
        })}
      />,
    );
    expect(screen.getByText(/cancelled by user/)).toBeDefined();
  });

  it("renders generic fallback for unknown event type", () => {
    render(
      <EventCard
        event={makeEvent({
          type: "unknown.event" as any,
          phase: "run",
          data: {},
        })}
      />,
    );
    expect(screen.getByText("unknown.event")).toBeDefined();
  });
});
