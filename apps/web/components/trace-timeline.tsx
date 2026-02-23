"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { TraceAttempt } from "@/lib/types";

interface TraceTimelineProps {
  attempts: TraceAttempt[];
  className?: string;
}

/**
 * Collapsible list showing each validation attempt with steps and verdict.
 * Client component because of the expand/collapse interaction.
 */
export function TraceTimeline({ attempts, className }: TraceTimelineProps) {
  if (!attempts.length) {
    return (
      <p className="text-sm text-white/40">No trace data available.</p>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {attempts.map((attempt) => (
        <AttemptEntry key={attempt.attempt_number} attempt={attempt} />
      ))}
    </div>
  );
}

function AttemptEntry({ attempt }: { attempt: TraceAttempt }) {
  const [expanded, setExpanded] = useState(false);
  const accepted = attempt.verdict?.is_accepted ?? false;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02]">
      {/* Header — always visible */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "size-2 rounded-full",
              accepted ? "bg-emerald-400" : "bg-red-400",
            )}
            aria-hidden
          />
          <span className="text-sm font-medium text-white">
            Attempt {attempt.attempt_number}
          </span>
          {attempt.error && (
            <span className="text-xs text-red-300 truncate max-w-48">
              {attempt.error}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {attempt.verdict && (
            <span
              className={cn(
                "text-xs font-medium",
                accepted ? "text-emerald-400" : "text-red-400",
              )}
            >
              {accepted ? "Accepted" : "Rejected"}
            </span>
          )}
          <span className="text-xs text-white/30">{_fmtTime(attempt.timestamp)}</span>
          <span className="text-white/40 text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-white/[0.04]">
          {/* Steps */}
          {attempt.steps.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium text-white/40 uppercase tracking-wider mb-2">
                Steps
              </p>
              <div className="space-y-1">
                {attempt.steps.map((step) => (
                  <div
                    key={step.name}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="flex items-center gap-2">
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          step.is_success ? "bg-emerald-400" : "bg-red-400",
                        )}
                      />
                      <span className="text-white/70 font-mono">{step.name}</span>
                    </span>
                    <span className="text-white/40">
                      {step.duration_seconds.toFixed(2)}s
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Verdict detail */}
          {attempt.verdict && (
            <div>
              <p className="text-xs font-medium text-white/40 uppercase tracking-wider mb-2">
                Verdict
              </p>
              <p className="text-xs text-white/60 leading-relaxed">
                {attempt.verdict.reason}
              </p>
              {(attempt.verdict.gates_failed ?? []).length > 0 && (
                <p className="mt-1 text-xs text-red-300">
                  Gates failed: {(attempt.verdict.gates_failed ?? []).join(", ")}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function _fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
