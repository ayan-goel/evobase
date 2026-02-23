"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getProposalsByRun, getRuns } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { OnboardingBanner } from "@/components/onboarding-banner";
import { ProposalCard } from "@/components/proposal-card";
import { ProposalDrawer } from "@/components/proposal-drawer";
import { RunPRDialog } from "@/components/run-pr-dialog";
import { RunStatusBadge } from "@/components/run-status-badge";
import { TriggerRunButton } from "@/components/trigger-run-button";
import type { ConfidenceLevel, Proposal, Run, RunEvent } from "@/lib/types";

type RunWithProposals = Run & { proposals: Proposal[] };

interface RepoRunListProps {
  repoId: string;
  initialRuns: RunWithProposals[];
  setupFailing?: boolean;
}

const POLL_INTERVAL_MS = 5000;
const CLEARED_IDS_KEY = (repoId: string) => `clearedRunIds:${repoId}`;

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
  const [clearedIds, setClearedIds] = useState<Set<string>>(new Set());
  const activeRunStatus = getActiveRunStatus(runs);

  // Load persisted cleared IDs on mount (client-only)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(CLEARED_IDS_KEY(repoId));
      if (stored) setClearedIds(new Set(JSON.parse(stored) as string[]));
    } catch {
      // ignore malformed localStorage
    }
  }, [repoId]);

  useEffect(() => {
    if (!hasActiveRun(runs)) return;

    const interval = setInterval(async () => {
      const updated = await fetchRunsWithProposals(repoId);
      setRuns(updated);
      if (!hasActiveRun(updated)) {
        clearInterval(interval);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [repoId, runs]);

  function handleQueued(runId: string) {
    setRuns((prev) => [
      {
        id: runId,
        repo_id: repoId,
        sha: null,
        status: "queued",
        compute_minutes: null,
        failure_step: null,
        commit_message: null,
        created_at: new Date().toISOString(),
        proposals: [],
      },
      ...prev,
    ]);
  }

  function handleClear() {
    const newCleared = new Set([...clearedIds, ...runs.map((r) => r.id)]);
    localStorage.setItem(CLEARED_IDS_KEY(repoId), JSON.stringify([...newCleared]));
    setClearedIds(newCleared);
  }

  function handleViewAll() {
    localStorage.removeItem(CLEARED_IDS_KEY(repoId));
    setClearedIds(new Set());
  }

  // Hide only runs that were explicitly cleared; active runs always visible
  const visibleRuns = runs.filter((r) => !clearedIds.has(r.id));

  const hiddenCount = runs.length - visibleRuns.length;

  return (
    <>
      <OnboardingBanner runs={runs} />

      <div className="mb-6 flex items-center gap-2">
        <TriggerRunButton
          repoId={repoId}
          onQueued={handleQueued}
          activeStatus={activeRunStatus}
        />
        {runs.length > 0 && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
          >
            Clear
          </button>
        )}
        {hiddenCount > 0 && (
          <button
            type="button"
            onClick={handleViewAll}
            className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
          >
            View all runs
          </button>
        )}
      </div>

      {visibleRuns.length === 0 ? (
        <EmptyRuns />
      ) : (
        <div className="space-y-4">
          {visibleRuns.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              proposals={run.proposals}
              repoId={repoId}
              setupFailing={setupFailing}
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
  opportunitiesFound: number;
}

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
  let opportunitiesFound = 0;

  let totalFiles = 0;
  let filesAnalysed = 0;
  let lastAnalysingFile = "";

  for (const ev of events) {
    phaseLabel = PHASE_LABELS[ev.phase] ?? phaseLabel;

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
      case "discovery.file.analysing":
        lastAnalysingFile = _truncatePath(ev.data.file as string);
        detail = totalFiles
          ? `Analysing file ${(ev.data.file_index as number) + 1} of ${totalFiles} — ${lastAnalysingFile}`
          : `Analysing ${lastAnalysingFile}`;
        break;
      case "discovery.file.analysed": {
        filesAnalysed += 1;
        const found = (ev.data.opportunities_found as number) ?? 0;
        opportunitiesFound += found;
        detail = totalFiles
          ? `Analysed ${filesAnalysed} of ${totalFiles} files — ${opportunitiesFound} opportunit${opportunitiesFound !== 1 ? "ies" : "y"} found`
          : `${opportunitiesFound} opportunit${opportunitiesFound !== 1 ? "ies" : "y"} found`;
        break;
      }
      case "discovery.completed":
        detail = `Discovery complete — ${opportunitiesFound} opportunit${opportunitiesFound !== 1 ? "ies" : "y"}`;
        break;
      case "patch.approach.started": {
        const opp = (ev.data.opportunity_index as number) ?? 0;
        const approach = (ev.data.approach_index as number) ?? 0;
        detail = `Opportunity ${opp + 1}, approach ${approach + 1}`;
        break;
      }
      case "patch.approach.completed":
        detail = "Patch generated";
        break;
      case "validation.candidate.started": {
        const idx = (ev.data.candidate_index as number) ?? 0;
        detail = `Validating candidate ${idx + 1}`;
        break;
      }
      case "validation.verdict": {
        const accepted = ev.data.is_accepted as boolean;
        detail = accepted ? "Candidate accepted" : "Candidate rejected";
        break;
      }
      case "selection.completed":
        detail = "Selection complete";
        break;
    }
  }

  return { phaseLabel, detail, opportunitiesFound };
}

function _truncatePath(path: string): string {
  if (!path) return "";
  const parts = path.split("/");
  if (parts.length <= 3) return path;
  return "…/" + parts.slice(-2).join("/");
}

// ---------------------------------------------------------------------------
// LiveRunSummary — compact live status for active run cards
// ---------------------------------------------------------------------------

function LiveRunSummary({ runId, repoId }: { runId: string; repoId: string }) {
  const { events } = useRunEvents(runId, true);

  const status = useMemo(() => deriveStatus(events), [events]);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
        </span>
        <span className="text-xs font-medium text-blue-300">{status.phaseLabel}</span>
        {status.opportunitiesFound > 0 && (
          <>
            <span className="text-white/15">·</span>
            <span className="text-xs text-emerald-400/70">
              {status.opportunitiesFound} opportunit{status.opportunitiesFound !== 1 ? "ies" : "y"}
            </span>
          </>
        )}
      </div>
      {status.detail && (
        <p className="text-xs text-white/35 pl-4">{status.detail}</p>
      )}
      <Link
        href={`/repos/${repoId}/runs/${runId}`}
        className="inline-block text-xs text-blue-400/60 hover:text-blue-400/80 transition-colors pl-4"
      >
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
  const counts: Record<string, number> = {};
  for (const p of proposals) {
    const key = p.confidence ?? "unknown";
    counts[key] = (counts[key] ?? 0) + 1;
  }
  const parts: string[] = [];
  for (const level of ["high", "medium", "low"] as ConfidenceLevel[]) {
    if (counts[level]) parts.push(`${counts[level]} ${level}`);
  }
  if (counts["unknown"]) parts.push(`${counts["unknown"]} unrated`);
  const label = `${proposals.length} proposal${proposals.length !== 1 ? "s" : ""}`;
  return parts.length > 0 ? `${label} — ${parts.join(", ")}` : label;
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
}: {
  run: Run;
  proposals: Proposal[];
  repoId: string;
  setupFailing: boolean;
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

      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-5 py-4 transition-colors hover:border-white/[0.12]">
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
            <span className="text-xs text-white/30">{_fmtDate(run.created_at)}</span>
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
