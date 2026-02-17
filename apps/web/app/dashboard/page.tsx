import Link from "next/link";
import { getRepos } from "@/lib/api";
import { Nav } from "@/components/nav";
import type { Repository } from "@/lib/types";

export const metadata = { title: "Dashboard — SelfOpt" };

/** Presentational component — tested in isolation with mock data. */
export function DashboardView({ repos }: { repos: Repository[] }) {
  return (
    <div className="min-h-screen pt-24 pb-16">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">
            Repositories
          </h1>
          <p className="mt-1.5 text-sm text-white/50">
            Connect a repository to start optimizing.
          </p>
        </div>

        {repos.length === 0 ? (
          <EmptyRepos />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {repos.map((repo) => (
              <RepoCard key={repo.id} repo={repo} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RepoCard({ repo }: { repo: Repository }) {
  return (
    <Link
      href={`/repos/${repo.id}`}
      className="group rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-5 hover:bg-white/[0.05] hover:border-white/[0.10] transition-all"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-white">
            {repo.github_repo_id
              ? `Repo #${repo.github_repo_id}`
              : `Repo ${repo.id.slice(0, 8)}`}
          </p>
          <p className="mt-0.5 text-xs text-white/40">
            {repo.default_branch} · {repo.package_manager ?? "unknown PM"}
          </p>
        </div>
        <span className="text-xs text-white/30 group-hover:text-white/50 transition-colors">
          →
        </span>
      </div>

      {(repo.build_cmd || repo.test_cmd) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {repo.build_cmd && <CommandChip cmd={repo.build_cmd} />}
          {repo.test_cmd && <CommandChip cmd={repo.test_cmd} />}
        </div>
      )}
    </Link>
  );
}

function CommandChip({ cmd }: { cmd: string }) {
  return (
    <span className="rounded-full border border-white/[0.06] bg-white/[0.04] px-2.5 py-0.5 text-xs font-mono text-white/50 truncate max-w-48">
      {cmd}
    </span>
  );
}

function EmptyRepos() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
      <p className="text-sm text-white/40">No repositories connected yet.</p>
      <p className="mt-1 text-xs text-white/25">
        Install the GitHub App to get started.
      </p>
    </div>
  );
}

/** RSC page — fetches data then delegates to DashboardView. */
export default async function DashboardPage() {
  let repos: Repository[] = [];

  try {
    repos = await getRepos();
  } catch {
    // API not reachable — show empty state rather than crashing
  }

  return (
    <>
      <Nav />
      <DashboardView repos={repos} />
    </>
  );
}
