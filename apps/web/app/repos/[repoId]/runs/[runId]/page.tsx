import Link from "next/link";
import { getRun, getRepo } from "@/lib/api-server";
import { NavWithUser } from "@/components/nav-server";
import { RunDetailView } from "@/components/run-detail/run-detail-view";
import type { Repository, Run } from "@/lib/types";

export const metadata = { title: "Run Detail — Coreloop" };

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ repoId: string; runId: string }>;
}) {
  const { repoId, runId } = await params;

  let repo: Repository | null = null;
  let run: Run | null = null;

  try {
    [repo, run] = await Promise.all([getRepo(repoId), getRun(runId)]);
  } catch {
    // API not reachable
  }

  if (!repo || !run) {
    return (
      <>
        <NavWithUser />
        <div className="min-h-screen pt-24 flex items-center justify-center">
          <p className="text-sm text-white/50">Run not found.</p>
        </div>
      </>
    );
  }

  const repoName = repo.github_full_name ?? `Repo ${repo.id.slice(0, 8)}`;

  return (
    <>
      <NavWithUser />
      <div className="min-h-screen pt-24 pb-16">
        <div className="mx-auto w-full max-w-4xl px-4">
          <nav className="mb-6 text-xs text-white/40" aria-label="Breadcrumb">
            <Link href="/dashboard" className="hover:text-white/70 transition-colors">
              Dashboard
            </Link>
            <span className="mx-2">/</span>
            <Link
              href={`/repos/${repoId}`}
              className="hover:text-white/70 transition-colors"
            >
              {repoName}
            </Link>
            <span className="mx-2">/</span>
            <span className="text-white/70">Run {run.id.slice(0, 8)}</span>
          </nav>

          <RunDetailView run={run} repoId={repoId} />
        </div>
      </div>
    </>
  );
}
