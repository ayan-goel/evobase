"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getRun } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { CancelRunButton } from "@/components/run-detail/cancel-run-button";
import { EventCard } from "@/components/run-detail/event-card";
import { FileAnalysisGrid } from "@/components/run-detail/file-analysis-grid";
import { RunStatusBadge } from "@/components/run-status-badge";
import type { Run, RunEvent, RunPhase, RunStatus } from "@/lib/types";

interface RunDetailViewProps {
  run: Run;
  repoId: string;
}

// Ordered phases used for the sidebar checklist
const PIPELINE_PHASES: { key: RunPhase | "done"; label: string }[] = [
  { key: "clone", label: "Clone" },
  { key: "baseline", label: "Baseline" },
  { key: "discovery", label: "Discover" },
  { key: "patching", label: "Patch" },
  { key: "validation", label: "Validate" },
  { key: "done", label: "Done" },
];

const PHASE_ORDER_INDEX: Record<string, number> = {
  clone: 0,
  detection: 0,
  baseline: 1,
  discovery: 2,
  patch: 3,
  patching: 3,
  validation: 4,
  selection: 4,
  run: 5,
  done: 5,
};

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
  const lastFetchRef = useRef(0);

  useEffect(() => {
    timelineEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(async () => {
      try {
        const updated = await getRun(run.id);
        setRun(updated);
        lastFetchRef.current = Date.now();
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [run.id, isActive]);

  useEffect(() => {
    if (isDone && isActive && Date.now() - lastFetchRef.current > 2000) {
      getRun(run.id)
        .then(setRun)
        .catch(() => {});
    }
  }, [isDone, isActive, run.id]);

  const { sha, msg } = useMemo(() => {
    const sha = run.sha ? run.sha.slice(0, 7) : "no sha";
    const msg = run.commit_message
      ? run.commit_message.length > 72
      : run.commit_message
    : null;

  const currentPhaseIdx = useMemo(() => {
    return currentPhase != null
      ? (PHASE_ORDER_INDEX[currentPhase] ?? -1)
      : isDone
        ? 5
        : -1;
  }, [currentPhase, isDone]);

  // Derive live stats from the event stream
  const stats = useMemo(() => _deriveStats(events), [events]);

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

      {/* ── Two-column body ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6 items-start">
        {/* ── Sidebar (sticky) ── */}
        <aside className="lg:sticky lg:top-6 space-y-4">
          {/* Phase checklist */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25 mb-3">
              Pipeline
            </p>
            <ol className="space-y-2">
              {PIPELINE_PHASES.map(({ key, label }, i) => {
                const phaseIdx = PHASE_ORDER_INDEX[key] ?? i;
                const isDonePhase = phaseIdx < currentPhaseIdx;
                const isCurrentPhase = phaseIdx === currentPhaseIdx;
                const isPending = phaseIdx > currentPhaseIdx;
                return (
                  <li key={key} className="flex items-center gap-2.5">
                    <PhaseIcon
                      done={isDonePhase}
                      active={isCurrentPhase}
                      pending={isPending}
                    />
                    <span
                      className={`text-sm ${
                        isCurrentPhase
                          ? "text-white/90 font-medium"
                          : isDonePhase
                            ? "text-white/40"
                            : "text-white/20"
                      }`}
                    >
                      {label}
                    </span>
                    {isCurrentPhase && isActive && (
                      <span className="ml-auto text-[9px] text-blue-400/60 font-mono uppercase tracking-wider">
                        active
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>

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
  const items: Array<
    { type: "header"; phase: string } | { type: "event"; event: RunEvent }
  > = useMemo(() => {
    const result: Array<
      { type: "header"; phase: string } | { type: "event"; event: RunEvent }
    > = [];

    // Pre-index all analysed events by file so the analysing row can be
    // promoted to the analysed state at the same timeline position.
    const analysedByFile = new Map<string, RunEvent>();
    for (const event of events) {
      if (event.type === "discovery.file.analysed") {
        const file = event.data.file as string | undefined;
        if (file) analysedByFile.set(file, event);
      }
    }
    // IDs of analysed events that have already been placed at the analysing
    // position — skip them when encountered in the normal pass.
    const skippedIds = new Set<string>();

    let lastPhase: string | null = null;

    for (const event of events) {
      if (skippedIds.has(event.id)) continue;

      const normPhase = _normalisePhase(event.phase);
      if (normPhase !== lastPhase) {
        result.push({ type: "header", phase: normPhase });
        lastPhase = normPhase;
      }

      if (event.type === "discovery.file.analysing") {
        const file = event.data.file as string | undefined;
        const analysed = file ? analysedByFile.get(file) : undefined;
        if (analysed) {
          // Promote the analysed event to this position; skip it later.
          skippedIds.add(analysed.id);
          result.push({ type: "event", event: analysed });
        } else {
          result.push({ type: "event", event });
        }
      } else {
        result.push({ type: "event", event });
      }
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

function PhaseIcon({
  done,
  active,
  pending,
}: {
  done: boolean;
  active: boolean;
  pending: boolean;
}) {
  if (done) {
    return (
      <svg
        className="h-4 w-4 shrink-0 text-emerald-400/60"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2.5}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  if (active) {
    return (
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/40" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-400" />
      </span>
    );
  }
  // pending — suppress TS unused-var warning by using the param implicitly
  void pending;
  return (
    <span className="h-4 w-4 shrink-0 rounded-full border border-white/[0.15] bg-transparent" />
  );
}

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
  let approachesStarted = 0;
  let candidatesAttempted = 0;
  let candidatesAccepted = 0;
  const analysedFiles = new Set<string>();
  const opportunitiesByFile = new Map<string, number>();

  for (const e of events) {
    if (e.type === "discovery.files.selected") {
      totalFiles = (e.data.count as number) ?? 0;
    } else if (e.type === "discovery.file.analysed") {
      const file = typeof e.data.file === "string" ? e.data.file : null;
      const count = (e.data.opportunities_found as number) ?? 0;
      if (file) {
        analysedFiles.add(file);
        opportunitiesByFile.set(file, count);
      }
    } else if (e.type === "patch.approach.started") {
      approachesStarted++;
    } else if (e.type === "validation.verdict") {
      candidatesAttempted++;
      if (e.data.accepted) candidatesAccepted++;
    }
  }

  return {
    totalFiles,
    filesAnalysed: analysedFiles.size,
    opportunitiesFound: Array.from(opportunitiesByFile.values()).reduce(
      (sum, count) => sum + count,
      0,
    ),
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
