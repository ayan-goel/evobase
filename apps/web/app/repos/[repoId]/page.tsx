import Link from "next/link";
import { getRepo, getRuns, getProposalsByRun } from "@/lib/api";
import { Nav } from "@/components/nav";
import { RunStatusBadge } from "@/components/run-status-badge";
import { ProposalCard } from "@/components/proposal-card";
import type { Proposal, Repository, Run } from "@/lib/types";

export const metadata = { title: "Repository — SelfOpt" };

interface RepoPageData {
  repo: Repository;
  runs: Array<Run & { proposals: Proposal[] }>;
}

/** Presentational view — tested in isolation with mock data. */
export function RepoView({ repo, runs }: RepoPageData) {
  return (
    <div className="min-h-screen pt-24 pb-16">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Breadcrumb */}
        <nav className="mb-6 text-xs text-white/40" aria-label="Breadcrumb">
          <Link href="/dashboard" className="hover:text-white/70 transition-colors">
            Dashboard
          </Link>
          <span className="mx-2">/</span>
          <span className="text-white/70">
            {repo.github_repo_id
              ? `Repo #${repo.github_repo_id}`
              : `Repo ${repo.id.slice(0, 8)}`}
          </span>
        </nav>

        {/* Repo header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">
              {repo.github_repo_id
                ? `Repo #${repo.github_repo_id}`
                : `Repo ${repo.id.slice(0, 8)}`}
            </h1>
            <p className="mt-1.5 text-sm text-white/50">
              {repo.default_branch} · {repo.package_manager ?? "unknown PM"}
            </p>
          </div>
          <Link
            href={`/repos/${repo.id}/settings`}
            className="shrink-0 rounded-full border border-white/12 bg-white/5 px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
          >
            Settings
          </Link>
        </div>

        {runs.length === 0 ? (
          <EmptyRuns />
        ) : (
          <div className="space-y-8">
            {runs.map((run) => (
              <RunSection key={run.id} run={run} proposals={run.proposals} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RunSection({
  run,
  proposals,
}: {
  run: Run;
  proposals: Proposal[];
}) {
  return (
    <section>
      {/* Run header */}
      <div className="mb-3 flex items-center gap-3">
        <RunStatusBadge status={run.status} />
        <span className="text-xs text-white/40 font-mono">
          {run.sha ? run.sha.slice(0, 7) : "no sha"}
        </span>
        <span className="text-xs text-white/30">{_fmtDate(run.created_at)}</span>
      </div>

      {proposals.length === 0 ? (
        <p className="text-sm text-white/30 pl-1">
          {run.status === "running" || run.status === "queued"
            ? "Run in progress…"
            : "No proposals generated."}
        </p>
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

/** RSC page — fetches data then delegates to RepoView. */
export default async function RepoPage({
  params,
}: {
  params: Promise<{ repoId: string }>;
}) {
  const { repoId } = await params;

  let repo: Repository | null = null;
  let runsWithProposals: Array<Run & { proposals: Proposal[] }> = [];

  try {
    [repo] = await Promise.all([getRepo(repoId)]);
    const runs = await getRuns(repoId);

    runsWithProposals = await Promise.all(
      runs.map(async (run) => {
        const proposals = await getProposalsByRun(run.id).catch(() => []);
        return { ...run, proposals };
      }),
    );
  } catch {
    // API not reachable — show fallback
  }

  if (!repo) {
    return (
      <>
        <Nav />
        <div className="min-h-screen pt-24 flex items-center justify-center">
          <p className="text-sm text-white/50">Repository not found.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <Nav />
      <RepoView repo={repo} runs={runsWithProposals} />
    </>
  );
}
