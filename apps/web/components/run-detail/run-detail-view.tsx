"use client";

import { useEffect, useRef, useState } from "react";
import { getRun } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { CancelRunButton } from "@/components/run-detail/cancel-run-button";
import { EventCard } from "@/components/run-detail/event-card";
import { PhaseProgress } from "@/components/run-detail/phase-progress";
import { RunStatusBadge } from "@/components/run-status-badge";
import type { Run, RunStatus } from "@/lib/types";

interface RunDetailViewProps {
  run: Run;
  repoId: string;
}

export function RunDetailView({ run: initialRun, repoId }: RunDetailViewProps) {
  const [run, setRun] = useState(initialRun);
  const isActive = run.status === "queued" || run.status === "running";
  const { events, currentPhase, isConnected, isDone } = useRunEvents(
    run.id,
    isActive,
  );
  const timelineEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(async () => {
      try {
        const updated = await getRun(run.id);
        setRun(updated);
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [run.id, isActive]);

  useEffect(() => {
    if (isDone && isActive) {
      getRun(run.id)
        .then(setRun)
        .catch(() => {});
    }
  }, [isDone, isActive, run.id]);

  const sha = run.sha ? run.sha.slice(0, 7) : "no sha";
  const msg = run.commit_message
    ? run.commit_message.length > 72
      ? run.commit_message.slice(0, 72) + "…"
      : run.commit_message
    : null;

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">
              Run {run.id.slice(0, 8)}
            </h1>
            <RunStatusBadge status={run.status} />
            {isActive && isConnected && (
              <span className="text-[10px] text-emerald-400/60 font-mono uppercase tracking-wider">
                live
              </span>
            )}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-sm text-white/40">
            <span className="font-mono">{sha}</span>
            {msg && <span className="text-white/30">— {msg}</span>}
            <span>·</span>
            <span>{_fmtDate(run.created_at)}</span>
          </div>
        </div>

        {isActive && (
          <CancelRunButton
            runId={run.id}
            onCancelled={() =>
              setRun((prev) => ({ ...prev, status: "failed" as RunStatus }))
            }
          />
        )}
      </div>

      {/* Phase progress */}
      <PhaseProgress currentPhase={currentPhase} isDone={!isActive} />

      {/* Event timeline */}
      <div className="mt-6">
        {events.length === 0 && isActive ? (
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
            <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
            <p className="mt-3 text-sm text-white/40">
              {run.status === "queued"
                ? "Waiting for worker to pick up this run…"
                : "Connecting to event stream…"}
            </p>
          </div>
        ) : events.length === 0 && !isActive ? (
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
            <p className="text-sm text-white/40">
              No events recorded for this run.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {events
              .filter((e) => e.type !== "heartbeat")
              .map((event, idx) => (
                <EventCard key={event.id || idx} event={event} />
              ))}
            <div ref={timelineEndRef} />
          </div>
        )}
      </div>
    </div>
  );
}

function _fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
