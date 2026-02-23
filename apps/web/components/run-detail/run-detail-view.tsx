"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getRun } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { CancelRunButton } from "@/components/run-detail/cancel-run-button";
import { EventCard } from "@/components/run-detail/event-card";
import { FileAnalysisGrid } from "@/components/run-detail/file-analysis-grid";
import { PhaseProgress } from "@/components/run-detail/phase-progress";
import { RunStatusBadge } from "@/components/run-status-badge";
import type { Run, RunEvent, RunPhase, RunStatus } from "@/lib/types";

interface RunDetailViewProps {
  run: Run;
  repoId: string;
}

const PHASE_LABELS: Record<string, string> = {
  clone: "Clone",
  detection: "Detection",
  baseline: "Baseline",
  discovery: "Discovery",
  patch: "Patching",
  patching: "Patching",
  validation: "Validation",
  selection: "Selection",
  run: "Run",
};

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

  // Derive live stats from the event stream
  const stats = useMemo(() => _deriveStats(events), [events]);

  // Build timeline groups (flat events with phase headers injected)
  const visibleEvents = useMemo(
    () => events.filter((e) => e.type !== "heartbeat"),
    [events],
  );

  return (
    <div>
      {/* ── Header ── */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold tracking-tight">
              Run {run.id.slice(0, 8)}
            </h1>
            <RunStatusBadge status={run.status} />
            {isActive && isConnected && (
              <span className="flex items-center gap-1.5 text-[10px] text-emerald-400/70 font-mono uppercase tracking-wider">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                </span>
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

      {/* ── Horizontal phase progress bar ── */}
      <div className="mb-6">
        <PhaseProgress currentPhase={currentPhase} isDone={!isActive} />
      </div>

      {/* ── Two-column body ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6 items-start">
        {/* ── Sidebar (sticky) — stats + file grid only ── */}
        <aside className="lg:sticky lg:top-6 space-y-4">
          {/* Live stats — only shown once there's something to report */}
          {(stats.totalFiles > 0 ||
            stats.candidatesAttempted > 0 ||
            stats.approachesStarted > 0) && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">
                Stats
              </p>

              {stats.totalFiles > 0 && (
                <StatRow
                  label="Files analysed"
                  value={`${stats.filesAnalysed} / ${stats.totalFiles}`}
                />
              )}
              {stats.opportunitiesFound > 0 && (
                <StatRow
                  label="Opportunities"
                  value={stats.opportunitiesFound}
                  accent="emerald"
                />
              )}
              {stats.approachesStarted > 0 && (
                <StatRow
                  label="Approaches tried"
                  value={stats.approachesStarted}
                />
              )}
              {stats.candidatesAttempted > 0 && (
                <StatRow
                  label="Accepted"
                  value={`${stats.candidatesAccepted} / ${stats.candidatesAttempted}`}
                  accent={stats.candidatesAccepted > 0 ? "emerald" : undefined}
                />
              )}
            </div>
          )}

          {/* File analysis grid (discovery phase only) */}
          {stats.totalFiles > 0 && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 space-y-3">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">
                File Analysis
              </p>
              <FileAnalysisGrid events={events} />
            </div>
          )}
        </aside>

        {/* ── Activity feed ── */}
        <div className="min-w-0">
          {visibleEvents.length === 0 && isActive ? (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-10 text-center">
              <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
              <p className="mt-3 text-sm text-white/40">
                {run.status === "queued"
                  ? "Waiting for worker to pick up this run…"
                  : "Connecting to event stream…"}
              </p>
            </div>
          ) : visibleEvents.length === 0 && !isActive ? (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-10 text-center">
              <p className="text-sm text-white/40">
                No events recorded for this run.
              </p>
            </div>
          ) : (
            <GroupedTimeline events={visibleEvents} isActive={isActive} />
          )}
          <div ref={timelineEndRef} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grouped timeline — inserts phase section headers at phase transitions
// ---------------------------------------------------------------------------

function GroupedTimeline({
  events,
  isActive,
}: {
  events: RunEvent[];
  isActive: boolean;
}) {
  const items: Array<{ type: "header"; phase: string } | { type: "event"; event: RunEvent }> =
    useMemo(() => {
      const result: Array<
        { type: "header"; phase: string } | { type: "event"; event: RunEvent }
      > = [];
      let lastPhase: string | null = null;

      for (const event of events) {
        const normPhase = _normalisePhase(event.phase);
        if (normPhase !== lastPhase) {
          result.push({ type: "header", phase: normPhase });
          lastPhase = normPhase;
        }
        result.push({ type: "event", event });
      }

      return result;
    }, [events]);

  return (
    <div className="space-y-1.5">
      {items.map((item, idx) => {
        if (item.type === "header") {
          return (
            <PhaseGroupHeader
              key={`header-${item.phase}-${idx}`}
              phase={item.phase}
            />
          );
        }
        return (
          <EventCard
            key={item.event.id || `evt-${idx}`}
            event={item.event}
          />
        );
      })}
      {isActive && (
        <div className="flex items-center gap-2 px-4 py-2 opacity-40">
          <span className="inline-block h-3 w-3 animate-spin rounded-full border border-white/30 border-t-white/70" />
          <span className="text-xs text-white/30 font-mono">waiting…</span>
        </div>
      )}
    </div>
  );
}

function PhaseGroupHeader({ phase }: { phase: string }) {
  return (
    <div className="flex items-center gap-3 pt-3 pb-1 first:pt-0">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-white/25">
        {PHASE_LABELS[phase] ?? phase}
      </span>
      <div className="flex-1 h-px bg-white/[0.06]" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar sub-components
// ---------------------------------------------------------------------------

function StatRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: "emerald";
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-white/35">{label}</span>
      <span
        className={`text-xs font-mono font-medium tabular-nums ${
          accent === "emerald" ? "text-emerald-400/80" : "text-white/60"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface RunStats {
  totalFiles: number;
  filesAnalysed: number;
  opportunitiesFound: number;
  approachesStarted: number;
  candidatesAttempted: number;
  candidatesAccepted: number;
}

function _deriveStats(events: RunEvent[]): RunStats {
  let totalFiles = 0;
  let filesAnalysed = 0;
  let opportunitiesFound = 0;
  let approachesStarted = 0;
  let candidatesAttempted = 0;
  let candidatesAccepted = 0;

  for (const e of events) {
    if (e.type === "discovery.files.selected") {
      totalFiles = (e.data.count as number) ?? 0;
    } else if (e.type === "discovery.file.analysed") {
      filesAnalysed++;
      opportunitiesFound += (e.data.opportunities_found as number) ?? 0;
    } else if (e.type === "patch.approach.started") {
      approachesStarted++;
    } else if (e.type === "validation.verdict") {
      candidatesAttempted++;
      if (e.data.accepted) candidatesAccepted++;
    }
  }

  return {
    totalFiles,
    filesAnalysed,
    opportunitiesFound,
    approachesStarted,
    candidatesAttempted,
    candidatesAccepted,
  };
}

function _normalisePhase(phase: string): string {
  if (phase === "patching") return "patch";
  if (phase === "selection") return "validation";
  if (phase === "detection") return "clone";
  return phase;
}

function _fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
