/**
 * /repos/[repoId]/settings — repo budget & schedule settings panel.
 *
 * Server component: fetches current settings and repo metadata, then
 * renders the SettingsForm client component for interactive editing.
 */

import Link from "next/link";
import { notFound } from "next/navigation";
import { NavWithUser } from "@/components/nav-server";
import { SettingsForm } from "@/components/settings-form";
import { DeleteRepoButton } from "@/components/delete-repo-button";
import { getRepo, getRepoSettings, getLLMModels } from "@/lib/api-server";

interface PageProps {
  params: Promise<{ repoId: string }>;
}

export default async function RepoSettingsPage({ params }: PageProps) {
  const { repoId } = await params;

  const [repo, settings, llmProviders] = await Promise.all([
    getRepo(repoId).catch(() => null),
    getRepoSettings(repoId).catch(() => null),
    getLLMModels().catch(() => []),
  ]);

  if (!repo || !settings) {
    notFound();
  }

  const repoLabel = repo.github_repo_id
    ? `repo #${repo.github_repo_id}`
    : repoId.slice(0, 8);

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      <NavWithUser />

      <div className="mx-auto w-full max-w-4xl px-4 pt-28 pb-20">
        {/* Breadcrumb */}
        <nav className="mb-8 flex items-center gap-2 text-sm text-white/40">
          <Link
            href="/dashboard"
            className="transition-colors hover:text-white/70"
          >
            Dashboard
          </Link>
          <span>/</span>
          <Link
            href={`/repos/${repoId}`}
            className="transition-colors hover:text-white/70"
          >
            {repoLabel}
          </Link>
          <span>/</span>
          <span className="text-white/70">Settings</span>
        </nav>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            Repository settings
          </h1>
          <p className="mt-1.5 text-sm text-white/50">
            Configure scheduling, compute budget, and auto-pause thresholds.
          </p>
        </div>

        {/* Settings card */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-sm">
          <SettingsForm repoId={repoId} initial={settings} llmProviders={llmProviders} repo={repo} />
        </div>

        {/* Auto-pause info */}
        <div className="mt-6 rounded-xl border border-white/6 bg-white/[0.02] px-5 py-4">
          <p className="text-xs font-medium text-white/50 uppercase tracking-wider mb-2">
            Auto-pause thresholds
          </p>
          <ul className="space-y-1.5 text-xs text-white/40">
            <li>
              <span className="text-white/60">3 consecutive setup failures</span>
              {" "}— install step fails and cannot recover.
            </li>
            <li>
              <span className="text-white/60">5 consecutive flaky runs</span>
              {" "}— tests only pass on retry, indicating a non-deterministic suite.
            </li>
          </ul>
        </div>

        {/* Danger zone */}
        <div className="mt-6 rounded-xl border border-red-500/20 bg-red-500/[0.03] px-5 py-4">
          <p className="text-xs font-medium text-red-400/70 uppercase tracking-wider mb-3">
            Danger zone
          </p>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-white/70">Remove this repository</p>
              <p className="mt-0.5 text-xs text-white/35">
                Deletes all runs, proposals, and settings from Coreloop.
                Your GitHub repository is not affected.
              </p>
            </div>
            <DeleteRepoButton repoId={repoId} repoLabel={repoLabel} />
          </div>
        </div>
      </div>
    </main>
  );
}
