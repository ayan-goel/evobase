"use client";

import { useState } from "react";
import type { RunEvent } from "@/lib/types";

interface EventCardProps {
  event: RunEvent;
}

export function EventCard({ event }: EventCardProps) {
  const renderer = EVENT_RENDERERS[event.type] ?? renderGeneric;
  return renderer(event);
}

// ---------------------------------------------------------------------------
// Per-event-type renderers
// ---------------------------------------------------------------------------

function renderCloneStarted(event: RunEvent) {
  return (
    <TimelineRow icon="📦" phase="Clone" ts={event.ts}>
      Cloning <Mono>{event.data.repo as string}</Mono>…
    </TimelineRow>
  );
}

function renderCloneCompleted(event: RunEvent) {
  const sha = event.data.sha as string | undefined;
  const msg = event.data.commit_message as string | undefined;
  return (
    <TimelineRow icon="✓" phase="Clone" ts={event.ts} success>
      Clone complete
      {sha && (
        <span className="ml-2 text-white/30 font-mono text-xs">{sha}</span>
      )}
      {msg && (
        <span className="ml-1.5 text-white/25 text-xs">— {truncate(msg, 60)}</span>
      )}
    </TimelineRow>
  );
}

function renderDetectionCompleted(event: RunEvent) {
  const { language, framework, package_manager, confidence } = event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="🔍" phase="Detection" ts={event.ts} success>
      <span>
        Detected <Badge>{language as string}</Badge>
        {framework && (
          <>
            {" / "}
            <Badge>{framework as string}</Badge>
          </>
        )}
        {package_manager && (
          <span className="text-white/30 text-xs ml-2">
            via {package_manager as string}
          </span>
        )}
        {confidence != null && (
          <span className="text-white/20 text-xs ml-2">
            ({Math.round((confidence as number) * 100)}% confidence)
          </span>
        )}
      </span>
    </TimelineRow>
  );
}

function renderBaselineAttemptStarted(event: RunEvent) {
  const { attempt, mode } = event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="▶" phase="Baseline" ts={event.ts}>
      Starting baseline attempt {attempt as number}{" "}
      <Badge variant={mode === "adaptive" ? "warn" : "default"}>
        {mode as string}
      </Badge>
    </TimelineRow>
  );
}

function renderBaselineStepCompleted(event: RunEvent) {
  const { step, exit_code, duration, success, stderr_tail, command } =
    event.data as Record<string, unknown>;
  const isOk = success as boolean;
  return (
    <ExpandableRow
      icon={isOk ? "✓" : "✗"}
      phase="Baseline"
      ts={event.ts}
      success={isOk}
      error={!isOk}
      summary={
        <>
          <Mono>{step as string}</Mono>{" "}
          {isOk ? (
            <span className="text-emerald-400/70">OK</span>
          ) : (
            <span className="text-red-400/70">FAILED (exit {exit_code as number})</span>
          )}{" "}
          <span className="text-white/20 text-xs">
            {duration as number}s
          </span>
        </>
      }
      detail={
        <>
          <p className="text-white/30 text-xs font-mono mb-1">$ {command as string}</p>
          {stderr_tail && (
            <pre className="text-xs text-red-300/60 whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
              {stderr_tail as string}
            </pre>
          )}
        </>
      }
    />
  );
}

function renderBaselineCompleted(event: RunEvent) {
  const { success, attempts, mode, failure_reason } = event.data as Record<string, unknown>;
  const isOk = success as boolean;
  return (
    <TimelineRow
      icon={isOk ? "✓" : "✗"}
      phase="Baseline"
      ts={event.ts}
      success={isOk}
      error={!isOk}
    >
      Baseline {isOk ? "passed" : "failed"}
      {!isOk && failure_reason && (
        <span className="text-red-300/60 text-xs ml-2">
          ({failure_reason as string})
        </span>
      )}
      {(attempts as number) > 1 && (
        <span className="text-white/20 text-xs ml-2">
          after {attempts as number} attempts ({mode as string})
        </span>
      )}
    </TimelineRow>
  );
}

function renderDiscoveryStarted(event: RunEvent) {
  const { llm_model } = event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="🧠" phase="Discovery" ts={event.ts}>
      Agent analyzing codebase
      {llm_model && (
        <span className="text-white/20 text-xs ml-2">
          using {llm_model as string}
        </span>
      )}
    </TimelineRow>
  );
}

function renderOpportunityFound(event: RunEvent) {
  const { type, location, rationale, approaches } = event.data as Record<string, unknown>;
  return (
    <ExpandableRow
      icon="💡"
      phase="Discovery"
      ts={event.ts}
      summary={
        <>
          Found opportunity: <Badge>{type as string}</Badge>{" "}
          <Mono>{location as string}</Mono>
        </>
      }
      detail={
        <>
          <p className="text-white/40 text-xs mb-2">{rationale as string}</p>
          {Array.isArray(approaches) && approaches.length > 0 && (
            <div className="text-xs text-white/30">
              <p className="font-medium text-white/40 mb-1">
                Approaches ({approaches.length}):
              </p>
              <ol className="list-decimal list-inside space-y-0.5">
                {(approaches as string[]).map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
            </div>
          )}
        </>
      }
    />
  );
}

function renderDiscoveryCompleted(event: RunEvent) {
  const { count } = event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="✓" phase="Discovery" ts={event.ts} success>
      Discovery complete — {count as number} opportunit{(count as number) === 1 ? "y" : "ies"} found
    </TimelineRow>
  );
}

function renderValidationVerdict(event: RunEvent) {
  const { opportunity, accepted, confidence, reason, gates_passed, gates_failed, approaches_tried } =
    event.data as Record<string, unknown>;
  const isOk = accepted as boolean;
  return (
    <ExpandableRow
      icon={isOk ? "✓" : "✗"}
      phase="Validation"
      ts={event.ts}
      success={isOk}
      error={!isOk}
      summary={
        <>
          <Mono>{opportunity as string}</Mono>{" "}
          {isOk ? (
            <span className="text-emerald-400/70">accepted</span>
          ) : (
            <span className="text-red-400/70">rejected</span>
          )}
          {confidence && (
            <Badge variant={confidence === "high" ? "success" : confidence === "medium" ? "warn" : "default"}>
              {confidence as string}
            </Badge>
          )}
          {(approaches_tried as number) > 1 && (
            <span className="text-white/20 text-xs ml-1">
              ({approaches_tried as number} approaches)
            </span>
          )}
        </>
      }
      detail={
        <>
          {reason && <p className="text-white/40 text-xs mb-2">{reason as string}</p>}
          {Array.isArray(gates_passed) && (gates_passed as string[]).length > 0 && (
            <p className="text-emerald-400/50 text-xs">
              Passed: {(gates_passed as string[]).join(", ")}
            </p>
          )}
          {Array.isArray(gates_failed) && (gates_failed as string[]).length > 0 && (
            <p className="text-red-400/50 text-xs">
              Failed: {(gates_failed as string[]).join(", ")}
            </p>
          )}
        </>
      }
    />
  );
}

function renderSelectionCompleted(event: RunEvent) {
  const { reason } = event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="🏆" phase="Selection" ts={event.ts} success>
      Best approach selected
      {reason && (
        <span className="text-white/30 text-xs ml-2">
          — {reason as string}
        </span>
      )}
    </TimelineRow>
  );
}

function renderRunCompleted(event: RunEvent) {
  const { proposals_created, candidates_attempted, accepted } =
    event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="🎉" phase="Done" ts={event.ts} success>
      Run complete — {proposals_created as number} proposal{(proposals_created as number) !== 1 ? "s" : ""} created
      <span className="text-white/20 text-xs ml-2">
        ({accepted as number}/{candidates_attempted as number} candidates accepted)
      </span>
    </TimelineRow>
  );
}

function renderRunFailed(event: RunEvent) {
  const { reason, error, failure_step, failure_reason_code } =
    event.data as Record<string, unknown>;
  return (
    <TimelineRow icon="✗" phase="Error" ts={event.ts} error>
      Run failed
      {failure_step && (
        <span className="text-red-300/60 text-xs ml-2">
          at {failure_step as string}
        </span>
      )}
      {(failure_reason_code || reason || error) && (
        <span className="text-red-300/50 text-xs ml-1">
          — {(failure_reason_code || reason || error) as string}
        </span>
      )}
    </TimelineRow>
  );
}

function renderRunCancelled(event: RunEvent) {
  return (
    <TimelineRow icon="⏹" phase="Cancelled" ts={event.ts} error>
      Run cancelled by user
    </TimelineRow>
  );
}

function renderGeneric(event: RunEvent) {
  return (
    <TimelineRow icon="·" phase={event.phase} ts={event.ts}>
      {event.type}
    </TimelineRow>
  );
}

const EVENT_RENDERERS: Record<string, (e: RunEvent) => JSX.Element> = {
  "clone.started": renderCloneStarted,
  "clone.completed": renderCloneCompleted,
  "detection.completed": renderDetectionCompleted,
  "baseline.attempt.started": renderBaselineAttemptStarted,
  "baseline.step.completed": renderBaselineStepCompleted,
  "baseline.completed": renderBaselineCompleted,
  "discovery.started": renderDiscoveryStarted,
  "discovery.opportunity.found": renderOpportunityFound,
  "discovery.completed": renderDiscoveryCompleted,
  "validation.verdict": renderValidationVerdict,
  "selection.completed": renderSelectionCompleted,
  "run.completed": renderRunCompleted,
  "run.failed": renderRunFailed,
  "run.cancelled": renderRunCancelled,
};

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

function TimelineRow({
  icon,
  phase,
  ts,
  success,
  error,
  children,
}: {
  icon: string;
  phase: string;
  ts: string;
  success?: boolean;
  error?: boolean;
  children: React.ReactNode;
}) {
  const time = ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  return (
    <div
      className={`
        flex items-start gap-3 rounded-lg border px-4 py-3 text-sm
        ${error
          ? "border-red-500/20 bg-red-500/[0.04]"
          : success
            ? "border-emerald-500/15 bg-emerald-500/[0.03]"
            : "border-white/[0.06] bg-white/[0.02]"
        }
      `}
    >
      <span className="shrink-0 w-5 text-center">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          {children}
        </div>
      </div>
      <span className="shrink-0 text-[10px] text-white/20 font-mono tabular-nums">
        {time}
      </span>
    </div>
  );
}

function ExpandableRow({
  icon,
  phase,
  ts,
  success,
  error,
  summary,
  detail,
}: {
  icon: string;
  phase: string;
  ts: string;
  success?: boolean;
  error?: boolean;
  summary: React.ReactNode;
  detail: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const time = ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";

  return (
    <div
      className={`
        rounded-lg border text-sm
        ${error
          ? "border-red-500/20 bg-red-500/[0.04]"
          : success
            ? "border-emerald-500/15 bg-emerald-500/[0.03]"
            : "border-white/[0.06] bg-white/[0.02]"
        }
      `}
    >
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg"
      >
        <span className="shrink-0 w-5 text-center">{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">{summary}</div>
        </div>
        <span className="shrink-0 text-[10px] text-white/20 font-mono tabular-nums">
          {time}
        </span>
        <span className="shrink-0 text-white/20 text-xs ml-1">
          {isOpen ? "▾" : "▸"}
        </span>
      </button>
      {isOpen && (
        <div className="px-4 pb-3 pl-12 border-t border-white/[0.04] pt-2">
          {detail}
        </div>
      )}
    </div>
  );
}

function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "warn";
}) {
  const colors = {
    default: "bg-white/10 text-white/60",
    success: "bg-emerald-500/15 text-emerald-400/80",
    warn: "bg-amber-500/15 text-amber-400/80",
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${colors[variant]}`}
    >
      {children}
    </span>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <code className="text-xs font-mono text-white/50">{children}</code>;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}
