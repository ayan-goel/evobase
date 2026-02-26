import Link from "next/link";
import { getInstallations, getRepos } from "@/lib/api-server";
import { NavWithUser } from "@/components/nav-server";
import { FrameworkBadge } from "@/components/framework-badge";
import type { Installation, Repository } from "@/lib/types";

export const metadata = { title: "Dashboard — Coreloop" };

/** Returns the most human-readable label for a repo. */
function repoDisplayName(repo: Repository): string {
  if (repo.github_full_name) return repo.github_full_name;
  if (repo.github_repo_id) return `Repo #${repo.github_repo_id}`;
  return `Repo ${repo.id.slice(0, 8)}`;
}

/** Presentational component — tested in isolation with mock data. */
export function DashboardView({
  repos,
  installations,
}: {
  repos: Repository[];
  installations: Installation[];
}) {
  // If a GitHub App installation already exists, skip the GitHub redirect and
  // go straight to the repo picker. Otherwise start the installation flow.
  const connectHref =
    installations.length > 0
      ? `/github/callback?installation_id=${installations[0].installation_id}`
      : "/github/install";

  return (
    <div className="min-h-screen pt-24 pb-16">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Page header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">
              Repositories
            </h1>
            <p className="mt-1.5 text-sm text-white/50">
              Connect a repository to start optimizing.
            </p>
          </div>
          <Link
            href={connectHref}
            className="shrink-0 rounded-full bg-white text-black h-9 px-5 text-sm font-semibold transition-colors hover:bg-white/90 inline-flex items-center justify-center"
          >
            Connect Repository
          </Link>
        </div>

        {repos.length === 0 ? (
          installations.length > 0 ? (
            <ResumeSetup installation={installations[0]} />
          ) : (
            <EmptyRepos />
          )
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

function RepoStatusBadge({
  status,
  setupFailing,
}: {
  status: string | null | undefined;
  setupFailing: boolean;
}) {
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-300">
        <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
        Running
      </span>
    );
  }
  if (status === "queued") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 text-xs font-medium text-white/60">
        <span className="h-1.5 w-1.5 rounded-full bg-white/40 animate-pulse" />
        Queued
      </span>
    );
  }
  if (setupFailing) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-400">
        Setup failing
      </span>
    );
  }
  return (
    <span className="text-xs text-white/30 group-hover:text-white/50 transition-colors">
      →
    </span>
  );
}

function setupFailureMessage(latestFailureStep?: string | null): string {
  if (latestFailureStep === "test") return "Tests are failing.";
  if (latestFailureStep === "build") return "Build is failing.";
  if (latestFailureStep === "install") return "Install step is failing.";
  return "Setup is failing.";
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
            {repoDisplayName(repo)}
          </p>
          <p className="mt-0.5 text-xs text-white/40">
            {repo.default_branch}
            {repo.root_dir ? ` · ${repo.root_dir}` : ""}
          </p>
          <div className="mt-1.5">
            <FrameworkBadge
              framework={repo.framework}
              packageManager={repo.package_manager}
              size="sm"
              showLabel
            />
          </div>
        </div>
        <RepoStatusBadge
          status={repo.latest_run_status}
          setupFailing={repo.setup_failing}
        />
      </div>

      {repo.setup_failing &&
        repo.latest_run_status !== "running" &&
        repo.latest_run_status !== "queued" && (
          <p className="mt-2 text-xs text-amber-400/70">
            {setupFailureMessage(repo.latest_failure_step)} Update the project directory in Settings →
          </p>
        )}

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

function ResumeSetup({ installation }: { installation: Installation }) {
  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-8 text-center">
      <p className="text-sm text-amber-400 font-medium">
        GitHub App connected — finish setting up your repositories
      </p>
      <p className="mt-2 text-xs text-white/40">
        You&apos;ve installed the GitHub App as{" "}
        <span className="text-white/60 font-mono">{installation.account_login}</span>
        , but haven&apos;t selected any repositories yet.
      </p>
      <Link
        href={`/github/callback?installation_id=${installation.installation_id}`}
        className="mt-5 inline-flex items-center justify-center rounded-full bg-white text-black h-9 px-5 text-sm font-semibold transition-colors hover:bg-white/90"
      >
        Select Repositories
      </Link>
    </div>
  );
}

function EmptyRepos() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
      <p className="text-sm text-white/40">No repositories connected yet.</p>
      <p className="mt-2 text-xs text-white/25">
        Connect a repository to start optimizing your code.
      </p>
      <Link
        href="/github/install"
        className="mt-4 inline-flex items-center justify-center rounded-full bg-white text-black h-9 px-5 text-sm font-semibold transition-colors hover:bg-white/90"
      >
        Connect Repository
      </Link>
    </div>
  );
}

/** RSC page — fetches data then delegates to DashboardView. */
export default async function DashboardPage() {
  let repos: Repository[] = [];
  let installations: Installation[] = [];

  await Promise.allSettled([
    getRepos().then((r) => { repos = r; }),
    getInstallations().then((i) => { installations = i; }),
  ]);

  return (
    <>
      <NavWithUser />
      <DashboardView repos={repos} installations={installations} />
    </>
  );
}
