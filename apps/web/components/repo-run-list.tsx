"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteRun, getProposalsByRun, getRuns } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { OnboardingBanner } from "@/components/onboarding-banner";
import { PhaseProgress } from "@/components/run-detail/phase-progress";
import { ProposalCard } from "@/components/proposal-card";
import { ProposalDrawer } from "@/components/proposal-drawer";
import { RunPRDialog } from "@/components/run-pr-dialog";
import { RunStatusBadge } from "@/components/run-status-badge";
import { TriggerRunButton } from "@/components/trigger-run-button";
import type { Proposal, Run, RunEvent, RunPhase } from "@/lib/types";

type RunWithProposals = Run & { proposals: Proposal[] };

interface RepoRunListProps {
  repoId: string;
  initialRuns: RunWithProposals[];
  setupFailing?: boolean;
}

const POLL_INTERVAL_MS = 5000;

function hasActiveRun(runs: RunWithProposals[]): boolean {
  return runs.some((r) => r.status === "queued" || r.status === "running");
}

function getActiveRunStatus(runs: RunWithProposals[]): Run["status"] | null {
  if (runs.some((r) => r.status === "running")) return "running";
  if (runs.some((r) => r.status === "queued")) return "queued";
  return null;
}

async function fetchRunsWithProposals(repoId: string): Promise<RunWithProposals[]> {
  const runs = await getRuns(repoId);
  return Promise.all(
    runs.map(async (run) => {
      const proposals = await getProposalsByRun(run.id).catch(() => []);
      return { ...run, proposals };
    }),
  );
}

export function RepoRunList({ repoId, initialRuns, setupFailing = false }: RepoRunListProps) {
  const [runs, setRuns] = useState<RunWithProposals[]>(initialRuns);
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const activeRunStatus = useMemo(() => getActiveRunStatus(runs), [runs]);

  useEffect(() => {
    if (!hasActiveRun(runs)) return;
  useEffect(() => {
    hasActiveRunRef.current = hasActiveRun(runs);
  }, [runs]);

  // Poll for updates only when repoId changes
  useEffect(() => {
    if (!hasActiveRunRef.current) return;

    const interval = setInterval(async () => {
      if (!hasActiveRunRef.current) {
        clearInterval(interval);
        return;
      }
      const updated = await fetchRunsWithProposals(repoId);
      setRuns(updated);
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [repoId]);

  function handleQueued(runId: string) {
    setRuns((prev) => [
      {
        id: runId,
        repo_id: repoId,
        sha: null,
    ]);
  }

  const handleEnterSelect = useCallback(() => {
    setIsSelectMode(true);
    setSelectedIds(new Set());
  }, []);

  const handleExitSelect = useCallback(() => {
    setIsSelectMode(false);
    setSelectedIds(new Set());
    setPendingDelete(false);
  }, []);

  const handleToggle = useCallback((runId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  }, [selectedIds]);

  const handleConfirmDelete = useCallback(async () => {
    setIsDeleting(true);
    const ids = [...selectedIds];
    await Promise.allSettled(ids.map((id) => deleteRun(id)));
      return next;
    });
    setPendingDelete(false);
    setIsSelectMode(false);
    setSelectedIds(new Set());
  }, [selectedIds]);

  return (
    <>
    setIsDeleting(false);
    setPendingDelete(false);
    setIsSelectMode(false);
    setSelectedIds(new Set());
  }

  return (
    <>
      <OnboardingBanner runs={runs} />

      <div className="mb-6 flex items-center gap-2 flex-wrap">
        <TriggerRunButton
          repoId={repoId}
          onQueued={handleQueued}
          activeStatus={activeRunStatus}
        />

        {!isSelectMode && runs.length > 0 && (
          <button
            type="button"
            onClick={handleEnterSelect}
            className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
          >
            Select
          </button>
        )}

        {isSelectMode && (
          <>
            <button
              type="button"
              onClick={handleExitSelect}
              className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => setPendingDelete(true)}
              disabled={selectedIds.size === 0}
              className="rounded-lg border border-red-500/30 bg-red-500/[0.08] px-4 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/15 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Delete{selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}
            </button>
          </>
        )}
      </div>

      {/* Delete confirmation dialog */}
      {pendingDelete && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-md"
            onClick={() => setPendingDelete(false)}
          />
          <div className="relative z-[110] w-full max-w-sm rounded-xl border border-white/[0.08] bg-[#111] p-6 shadow-2xl">
            <h2 className="text-sm font-semibold text-white">Delete runs?</h2>
            <p className="mt-2 text-xs text-white/50">
              Are you sure you want to delete{" "}
              <span className="text-white/80 font-medium">
                {selectedIds.size} run{selectedIds.size !== 1 ? "s" : ""}
              </span>
              ? This cannot be undone.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPendingDelete(false)}
                disabled={isDeleting}
                className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="rounded-lg border border-red-500/30 bg-red-500/[0.08] px-4 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-40"
              >
                {isDeleting ? "Deleting…" : "Yes, delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {runs.length === 0 ? (
        <EmptyRuns />
      ) : (
        <div className="space-y-4">
          {runs.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              proposals={run.proposals}
              repoId={repoId}
              setupFailing={setupFailing}
              isSelectMode={isSelectMode}
              isSelected={selectedIds.has(run.id)}
              onToggleSelect={() => handleToggle(run.id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

const FAILURE_MESSAGES: Record<string, { title: string; hint: string }> = {
  install: {
    title: "Install failed",
    hint: "Your install command could not complete. Check your project directory and install command in Settings.",
  },
  build: {
    title: "Build is failing",
    hint: "Fix your build errors, then push a commit to re-run the analysis automatically.",
  },
  test: {
    title: "Tests are failing",
    hint: "Fix your failing tests, then push a commit to re-run the analysis automatically.",
  },
  unknown: {
    title: "Setup failed",
    hint: "A pipeline step could not complete. Check your commands in Settings.",
  },
};

// ---------------------------------------------------------------------------
// Live status derivation
// ---------------------------------------------------------------------------

interface DerivedStatus {
  phaseLabel: string;
  detail: string;
  currentPhase: RunPhase | null;
  opportunitiesFound: number;
  approachesTested: number;
  candidatesValidated: number;
  candidatesAccepted: number;
  totalFiles: number;
  filesAnalysed: number;
}

// Phases in pipeline order — used to ensure currentPhase only advances forward.
const PHASE_ORDER: RunPhase[] = [
  "clone", "detection", "baseline", "discovery",
  "patching", "validation", "selection", "run",
];

const PHASE_LABELS: Record<string, string> = {
  clone: "Cloning repository",
  detection: "Detecting framework",
  baseline: "Running baseline",
  discovery: "Analysing files",
  patching: "Generating patches",
  validation: "Validating candidates",
  selection: "Selecting best patches",
  run: "Finishing up",
};

function deriveStatus(events: RunEvent[]): DerivedStatus {
  let phaseLabel = "Starting up";
  let detail = "";
  let currentPhase: RunPhase | null = null;
  let highestPhaseIdx = -1;
  let opportunitiesFound = 0;
  let approachesTested = 0;
  let candidatesValidated = 0;
  let candidatesAccepted = 0;
  let totalFiles = 0;
  let filesAnalysed = 0;

  for (const ev of events) {
    phaseLabel = PHASE_LABELS[ev.phase] ?? phaseLabel;

    // Advance currentPhase monotonically — never go backwards.
    const evPhaseIdx = PHASE_ORDER.indexOf(ev.phase as RunPhase);
    if (evPhaseIdx > highestPhaseIdx) {
      highestPhaseIdx = evPhaseIdx;
      currentPhase = ev.phase as RunPhase;
    }

    switch (ev.type) {
      case "clone.started":
        detail = "Cloning repository…";
        break;
      case "clone.completed": {
        const sha = (ev.data.sha as string) ?? "";
        detail = sha ? `Cloned at ${sha}` : "Clone complete";
        break;
      }
      case "detection.completed":
        detail = (ev.data.framework as string)
          ? `Detected ${ev.data.framework}`
          : "Detection complete";
        break;
      case "baseline.attempt.started":
        detail = "Running pipeline…";
        break;
      case "baseline.step.completed": {
        const step = (ev.data.step_name as string) ?? "";
        const ok = ev.data.is_success as boolean;
        if (step) detail = ok ? `${step} passed` : `${step} failed`;
        break;
      }
      case "baseline.completed":
        detail = "Baseline complete";
        break;
      case "discovery.files.selected":
        totalFiles = (ev.data.count as number) ?? 0;
        detail = `Selected ${totalFiles} file${totalFiles !== 1 ? "s" : ""} to analyse`;
        break;
      case "discovery.file.analysing": {
        const fileIdx = (ev.data.file_index as number) ?? 0;
        const file = _truncatePath(ev.data.file as string);
        detail = totalFiles
          ? `Analysing file ${fileIdx + 1} of ${totalFiles} — ${file}`
          : `Analysing ${file}`;
        break;
      }
      case "discovery.file.analysed": {
        filesAnalysed += 1;
        const found = (ev.data.opportunities_found as number) ?? 0;
        opportunitiesFound += found;
        detail = totalFiles
          ? `Analysed ${filesAnalysed} of ${totalFiles} files`
          : `${opportunitiesFound} opportunit${opportunitiesFound !== 1 ? "ies" : "y"} found`;
        break;
      }
      case "discovery.completed":
        detail = `Discovery complete`;
        break;
      case "patch.approach.started":
        approachesTested += 1;
        detail = `Generating approach ${approachesTested}`;
        break;
      case "patch.approach.completed":
        detail = "Approach ready";
        break;
      case "validation.candidate.started": {
        const idx = (ev.data.candidate_index as number) ?? 0;
        detail = `Validating candidate ${idx + 1}`;
        break;
      }
      case "validation.verdict": {
        candidatesValidated += 1;
        const accepted = ev.data.is_accepted as boolean;
        if (accepted) candidatesAccepted += 1;
        detail = accepted ? "Candidate accepted ✓" : "Candidate rejected";
        break;
      }
      case "selection.completed":
        detail = "Selection complete";
        break;
    }
  }

  return {
    phaseLabel,
    detail,
    currentPhase,
    opportunitiesFound,
    approachesTested,
    candidatesValidated,
    candidatesAccepted,
    totalFiles,
    filesAnalysed,
  };
}

// LiveRunSummary — compact live status for active run cards
// ---------------------------------------------------------------------------

const LiveRunSummary = React.memo(function LiveRunSummary({ runId, repoId }: { runId: string; repoId: string }) {
  const { events, isDone } = useRunEvents(runId, true);
  const status = useMemo(() => deriveStatus(events), [events]);

// ---------------------------------------------------------------------------
// LiveRunSummary — compact live status for active run cards
// ---------------------------------------------------------------------------

function LiveRunSummary({ runId, repoId }: { runId: string; repoId: string }) {
  const { events, isDone } = useRunEvents(runId, true);
  const status = useMemo(() => deriveStatus(events), [events]);

  // Use the highest phase seen across all events (monotonically advancing).
  // Fall back to "clone" so the bar always shows at least the first segment
  // active while the SSE connection is establishing.
  const currentPhase: RunPhase = status.currentPhase ?? "clone";

  const stats: { label: string; value: number | string; show: boolean }[] = [
    {
      label: "Opportunities",
      value: status.opportunitiesFound,
      show: status.opportunitiesFound > 0,
    },
    {
      label: "Approaches",
      value: status.approachesTested,
      show: status.approachesTested > 0,
    },
    {
      label: "Validated",
      value: status.candidatesValidated,
      show: status.candidatesValidated > 0,
    },
    {
      label: "Accepted",
      value: status.candidatesAccepted,
      show: status.candidatesValidated > 0,
    },
  ];

  const visibleStats = stats.filter((s) => s.show);

  return (
    <div className="space-y-4">
      {/* Phase progress bar */}
      <PhaseProgress currentPhase={currentPhase} isDone={isDone} />

      {/* Current action */}
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
        </span>
        <span className="text-xs text-blue-300/80 font-medium">{status.phaseLabel}</span>
        {status.detail && (
          <>
            <span className="text-white/15">·</span>
            <span className="text-xs text-white/35 truncate">{status.detail}</span>
          </>
        )}
      </div>

      {/* Live stats */}
      {visibleStats.length > 0 && (
        <div className="flex items-center gap-4 flex-wrap">
          {visibleStats.map((s) => (
            <div key={s.label} className="flex flex-col gap-0.5">
              <span className="text-[10px] font-medium uppercase tracking-widest text-white/25">
                {s.label}
              </span>
              <span className="text-sm font-semibold tabular-nums text-white/70">
                {s.value}
              </span>
            </div>
          ))}
      </Link>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Terminal run summary helpers
        View live details →
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Terminal run summary helpers
// ---------------------------------------------------------------------------

function _confidenceBreakdown(proposals: Proposal[]): string {
  if (proposals.length === 0) return "No opportunities";
  return `${proposals.length} proposal${proposals.length !== 1 ? "s" : ""}`;
}

function _prStatusSummary(proposals: Proposal[]): string | null {
  if (proposals.length === 0) return null;
  const withPr = proposals.filter((p) => p.pr_url).length;
  if (withPr === 0) return null;
  if (withPr === proposals.length) return "All PRs created";
  return `${withPr} of ${proposals.length} PRs created`;
}

// ---------------------------------------------------------------------------
// RunCard
// ---------------------------------------------------------------------------

function RunCard({
  run,
  proposals,
  repoId,
  setupFailing,
  isSelectMode,
  isSelected,
  onToggleSelect,
}: {
  run: Run;
  proposals: Proposal[];
  repoId: string;
  setupFailing: boolean;
  isSelectMode?: boolean;
  isSelected?: boolean;
  onToggleSelect?: () => void;
}) {
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [prDialogOpen, setPrDialogOpen] = useState(false);
  const [runPrUrl, setRunPrUrl] = useState<string | null>(run.pr_url ?? null);

  const sha = run.sha ? run.sha.slice(0, 7) : "no sha";
  const msg = run.commit_message
    ? run.commit_message.length > 72
      ? run.commit_message.slice(0, 72) + "…"
      : run.commit_message
    : null;

  const isActive = run.status === "running" || run.status === "queued";
  const isTerminal = run.status === "completed" || run.status === "failed";

  const showPrButton = isTerminal && run.status === "completed" && proposals.length > 0;

  return (
    <>
      <ProposalDrawer
        proposal={selectedProposal}
        onClose={() => setSelectedProposal(null)}
      />
      {showPrButton && (
        <RunPRDialog
          isOpen={prDialogOpen}
          onClose={() => setPrDialogOpen(false)}
          repoId={repoId}
          runId={run.id}
          proposals={proposals}
          onPRCreated={setRunPrUrl}
        />
      )}

      <div className="flex items-start gap-3">
        {isSelectMode && (
          <button
            type="button"
            aria-label={isSelected ? "Deselect run" : "Select run"}
            onClick={onToggleSelect}
            className="mt-4 shrink-0 flex h-4 w-4 items-center justify-center rounded border border-white/20 bg-white/[0.04] transition-colors hover:border-white/40 focus:outline-none"
          >
            {isSelected && (
              <span className="block h-2 w-2 rounded-sm bg-red-400" />
            )}
          </button>
        )}

      <div className="flex-1 rounded-xl border border-white/[0.07] bg-white/[0.02] px-5 py-4 transition-colors hover:border-white/[0.12]">
        {/* Header row */}
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            href={`/repos/${repoId}/runs/${run.id}`}
            className="flex items-center gap-3 flex-wrap group cursor-pointer flex-1 min-w-0"
          >
            <RunStatusBadge status={run.status} />
            <span className="text-xs text-white/40 font-mono group-hover:text-white/60 transition-colors">
              {sha}
              {msg && (
                <span className="text-white/30 font-sans ml-1.5 group-hover:text-white/50">— {msg}</span>
              )}
            </span>
            <span suppressHydrationWarning className="text-xs text-white/30">{_fmtDate(run.created_at)}</span>
            <span className="text-[10px] text-white/20 group-hover:text-white/40 transition-colors">
              View details →
            </span>
          </Link>

          {/* PR button — shown for completed runs with proposals */}
          {showPrButton && (
            runPrUrl ? (
              <a
                href={runPrUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 rounded-lg border border-emerald-500/25 bg-emerald-500/[0.08] px-3 py-1 text-xs font-medium text-emerald-300 hover:bg-emerald-500/15 transition-colors"
              >
                View PR →
              </a>
            ) : (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setPrDialogOpen(true); }}
                className="shrink-0 rounded-lg border border-white/15 bg-white/[0.05] px-3 py-1 text-xs font-medium text-white/60 hover:bg-white/[0.09] hover:text-white/80 transition-colors"
              >
                Open PR
              </button>
            )
          )}
        </div>

        {/* Meta row — only for terminal runs */}
        {isTerminal && (
          <div className="mt-2 flex items-center gap-2 flex-wrap text-xs text-white/30">
            {run.status === "completed" ? (
              <span>{_confidenceBreakdown(proposals)}</span>
            ) : run.failure_step ? (
              <span className="text-amber-400/60">
                {FAILURE_MESSAGES[run.failure_step]?.title ?? "Setup failed"}
              </span>
            ) : (
              <span className="text-red-400/50">Run failed</span>
            )}
            {_prStatusSummary(proposals) && (
              <>
                <span className="text-white/15">·</span>
                <span className="text-emerald-400/50">{_prStatusSummary(proposals)}</span>
              </>
            )}
            {run.compute_minutes != null && run.compute_minutes > 0 && (
              <>
                <span className="text-white/15">·</span>
                <span>~{run.compute_minutes.toFixed(1)} min compute</span>
              </>
            )}
          </div>
        )}

        {/* Body */}
        <div className="mt-3">
          {proposals.length === 0 ? (
            <>
              {isActive ? (
                <LiveRunSummary runId={run.id} repoId={repoId} />
              ) : run.failure_step ? (
                <BaselineFailureMessage failureStep={run.failure_step} repoId={repoId} />
              ) : run.status === "failed" && setupFailing ? (
                <p className="text-sm text-amber-400/70">
                  Setup failed — install step could not run.{" "}
                  <a
                    href={`/repos/${repoId}/settings`}
                    className="underline underline-offset-2 hover:text-amber-400 transition-colors"
                  >
                    Set a project directory in Settings →
                  </a>
                </p>
              ) : (
                <p className="text-sm text-white/30">No opportunities found this run.</p>
              )}
            </>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {proposals.map((proposal) => (
                <ProposalCard
                  key={proposal.id}
                  proposal={proposal}
                  onSelect={() => setSelectedProposal(proposal)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
      </div>
    </>
  );
}

function BaselineFailureMessage({
  failureStep,
  repoId,
}: {
  failureStep: string;
  repoId: string;
}) {
  const { title, hint } = FAILURE_MESSAGES[failureStep] ?? FAILURE_MESSAGES.unknown;
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-4 py-3">
      <p className="text-sm font-medium text-amber-400">{title}</p>
      <p className="mt-0.5 text-xs text-amber-300/70">
        {hint}{" "}
        <a
          href={`/repos/${repoId}/settings`}
          className="underline underline-offset-2 hover:text-amber-300 transition-colors"
        >
          Settings →
        </a>
      </p>
    </div>
  );
}

function EmptyRuns() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
      <p className="text-sm text-white/40">No runs yet.</p>
      <p className="mt-1 text-xs text-white/25">
        Trigger a run from the API or wait for the nightly schedule.
      </p>
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
