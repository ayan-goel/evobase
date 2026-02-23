import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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
