"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getProposalsByRun, getRuns } from "@/lib/api";
import { OnboardingBanner } from "@/components/onboarding-banner";
import { ProposalCard } from "@/components/proposal-card";
import { RunStatusBadge } from "@/components/run-status-badge";
import { TriggerRunButton } from "@/components/trigger-run-button";
import type { Proposal, Run } from "@/lib/types";

type RunWithProposals = Run & { proposals: Proposal[] };

interface RepoRunListProps {
  repoId: string;
  initialRuns: RunWithProposals[];
  setupFailing?: boolean;
}

const POLL_INTERVAL_MS = 5000;
const HIDE_BEFORE_KEY = (repoId: string) => `hideBefore:${repoId}`;

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
  const [hideBefore, setHideBefore] = useState<number | null>(null);
  const activeRunStatus = getActiveRunStatus(runs);

  // Load persisted hideBefore on mount (client-only)
  useEffect(() => {
    const stored = localStorage.getItem(HIDE_BEFORE_KEY(repoId));
    if (stored) setHideBefore(Number(stored));
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
    const ts = Date.now();
    localStorage.setItem(HIDE_BEFORE_KEY(repoId), String(ts));
    setHideBefore(ts);
  }

  function handleViewAll() {
    localStorage.removeItem(HIDE_BEFORE_KEY(repoId));
    setHideBefore(null);
  }

  // Always show active (queued/running) runs regardless of hideBefore
  const visibleRuns = hideBefore
    ? runs.filter(
        (r) =>
          r.status === "queued" ||
          r.status === "running" ||
          new Date(r.created_at).getTime() >= hideBefore,
      )
    : runs;

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
  const sha = run.sha ? run.sha.slice(0, 7) : "no sha";
  const msg = run.commit_message
    ? run.commit_message.length > 72
      ? run.commit_message.slice(0, 72) + "…"
      : run.commit_message
    : null;

  const isActive = run.status === "running" || run.status === "queued";
  const isTerminal = run.status === "completed" || run.status === "failed";

  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-5 py-4 transition-colors hover:border-white/[0.12]">
      {/* Header row */}
      <Link
        href={`/repos/${repoId}/runs/${run.id}`}
        className="flex items-center gap-3 flex-wrap group cursor-pointer"
      >
        <RunStatusBadge status={run.status} />
        <span className="text-xs text-white/40 font-mono group-hover:text-white/60 transition-colors">
          {sha}
          {msg && (
            <span className="text-white/30 font-sans ml-1.5 group-hover:text-white/50">— {msg}</span>
          )}
        </span>
        <span className="text-xs text-white/30">{_fmtDate(run.created_at)}</span>
        <span className="text-[10px] text-white/20 group-hover:text-white/40 transition-colors ml-auto">
          View details →
        </span>
      </Link>

      {/* Meta row — only for terminal runs */}
      {isTerminal && (
        <div className="mt-2 flex items-center gap-2 text-xs text-white/30">
          {run.status === "completed" ? (
            <span>
              {proposals.length > 0
                ? `${proposals.length} proposal${proposals.length !== 1 ? "s" : ""} found`
                : "No opportunities"}
            </span>
          ) : run.failure_step ? (
            <span className="text-amber-400/60">
              {FAILURE_MESSAGES[run.failure_step]?.title ?? "Setup failed"}
            </span>
          ) : (
            <span className="text-red-400/50">Run failed</span>
          )}
          {run.compute_minutes != null && (
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
              <Link
                href={`/repos/${repoId}/runs/${run.id}`}
                className="text-sm text-blue-400/60 hover:text-blue-400/80 transition-colors"
              >
                View live progress →
              </Link>
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
              <ProposalCard key={proposal.id} proposal={proposal} />
            ))}
          </div>
        )}
      </div>
    </div>
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
