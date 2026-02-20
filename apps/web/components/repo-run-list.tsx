"use client";

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

function hasActiveRun(runs: RunWithProposals[]): boolean {
  return runs.some((r) => r.status === "queued" || r.status === "running");
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

  return (
    <>
      <OnboardingBanner runs={runs} />

      <div className="mb-8 flex shrink-0 items-center gap-2 justify-end">
        <TriggerRunButton repoId={repoId} onQueued={handleQueued} />
      </div>

      {runs.length === 0 ? (
        <EmptyRuns />
      ) : (
        <div className="space-y-8">
          {runs.map((run) => (
            <RunSection
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

function RunSection({
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

  return (
    <section>
      <div className="mb-3 flex items-center gap-3 flex-wrap">
        <RunStatusBadge status={run.status} />
        <span className="text-xs text-white/40 font-mono">
          {sha}
          {msg && (
            <span className="text-white/30 font-sans ml-1.5">— {msg}</span>
          )}
        </span>
        <span className="text-xs text-white/30">{_fmtDate(run.created_at)}</span>
      </div>

      {proposals.length === 0 ? (
        <div className="pl-1">
          {run.status === "running" || run.status === "queued" ? (
            <p className="text-sm text-white/30">Run in progress…</p>
          ) : run.failure_step ? (
            <BaselineFailureMessage
              failureStep={run.failure_step}
              repoId={repoId}
            />
          ) : setupFailing ? (
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
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {proposals.map((proposal) => (
            <ProposalCard key={proposal.id} proposal={proposal} />
          ))}
        </div>
      )}
    </section>
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
