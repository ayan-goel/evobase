import Link from "next/link";
import { getRepo, getRuns, getProposalsByRun } from "@/lib/api-server";
import { NavWithUser } from "@/components/nav-server";
import { RepoRunList } from "@/components/repo-run-list";
import { FrameworkBadge } from "@/components/framework-badge";
import type { Proposal, Repository, Run } from "@/lib/types";

export const metadata = { title: "Repository — Coreloop" };

/** Returns the most human-readable label for a repo. */
function repoDisplayName(repo: Repository): string {
  if (repo.github_full_name) return repo.github_full_name;
  if (repo.github_repo_id) return `Repo #${repo.github_repo_id}`;
  return `Repo ${repo.id.slice(0, 8)}`;
}

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
          <span className="text-white/70">{repoDisplayName(repo)}</span>
        </nav>

        {/* Repo header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">
              {repoDisplayName(repo)}
            </h1>
            <div className="mt-1.5 flex items-center gap-3 text-sm text-white/50">
              <span>{repo.default_branch}</span>
              <span>·</span>
              <FrameworkBadge
                framework={repo.framework}
                packageManager={repo.package_manager}
                size="md"
                showLabel
              />
            </div>
          </div>
          <Link
            href={`/repos/${repo.id}/settings`}
            className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
          >
            Settings
          </Link>
        </div>

        <RepoRunList
          repoId={repo.id}
          initialRuns={runs}
          setupFailing={repo.setup_failing}
        />
      </div>
    </div>
  );
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
    const [repo_resolved, runs] = await Promise.all([getRepo(repoId), getRuns(repoId)]);
    repo = repo_resolved;

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
        <NavWithUser />
        <div className="min-h-screen pt-24 flex items-center justify-center">
          <p className="text-sm text-white/50">Repository not found.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <NavWithUser />
      <RepoView repo={repo} runs={runsWithProposals} />
    </>
  );
}
