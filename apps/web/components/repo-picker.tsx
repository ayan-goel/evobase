"use client";

import { useCallback, useEffect, memo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  connectRepo,
  getInstallationRepos,
  getMe,
} from "@/lib/api";
import type { GitHubRepo } from "@/lib/types";
import { useDetectFramework } from "@/hooks/use-detect-framework";
import { FrameworkBadge } from "@/components/framework-badge";

interface RepoPickerProps {
  installationId: number;
}

interface RepoRowProps {
  repo: GitHubRepo;
  installationId: number;
  isSelected: boolean;
  rootDir: string;
  onToggle: (repoId: number) => void;
  onRootDirChange: (repoId: number, value: string) => void;
}

const RepoRow = memo(function RepoRow({
  repo,
  installationId,
  isSelected,
  rootDir,
  onToggle,
  onRootDirChange,
}: RepoRowProps) {
  const { result, isDetecting } = useDetectFramework(
    installationId,
    isSelected ? repo.full_name : null,
    rootDir,
  );

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 transition-colors hover:bg-white/[0.05]">
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggle(repo.github_repo_id)}
          className="h-4 w-4 rounded border-white/20 bg-white/5 text-white accent-white"
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {repo.full_name}
          </p>
          <p className="text-xs text-white/40">
            {repo.default_branch}
            {repo.private && " · private"}
          </p>
        </div>
      </label>

      {isSelected && (
        <div className="mt-3 pl-7">
          <label className="block text-xs text-white/40 mb-1">
            Project directory{" "}
            <span className="text-white/25">(optional — leave blank for repo root)</span>
          </label>
          <input
            type="text"
            value={rootDir}
            onChange={(e) => onRootDirChange(repo.github_repo_id, e.target.value)}
            placeholder="e.g. apps/web, packages/backend"
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
          />
          <p className="mt-1 text-xs text-white/25">
            For monorepos: specify the sub-project folder that contains{" "}
            <code className="text-white/35">package.json</code> or{" "}
            <code className="text-white/35">pyproject.toml</code>.
          </p>

          <div className="mt-2 h-6 flex items-center">
            {isDetecting && (
              <span className="text-xs text-white/30 animate-pulse">Detecting framework…</span>
            )}
            {!isDetecting && result && (result.framework || result.package_manager) && (
              <FrameworkBadge
                framework={result.framework}
                packageManager={result.package_manager}
                size="sm"
                showLabel
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
});

export function RepoPicker({ installationId }: RepoPickerProps) {
  const router = useRouter();
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // Per-repo root_dir overrides: map of github_repo_id → directory string
  const [rootDirs, setRootDirs] = useState<Record<number, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [repoList, me] = await Promise.all([
          getInstallationRepos(installationId),
          getMe(),
        ]);
        setRepos(repoList);
        setOrgId(me.org_id);
      } catch (err: any) {
        setError(err.message ?? "Failed to load repositories");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [installationId]);

  const toggleRepo = useCallback((repoId: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(repoId)) next.delete(repoId);
      else next.add(repoId);
      return next;
    });
  }, []);

  const setRootDir = useCallback((repoId: number, value: string) => {
    setRootDirs((prev) => ({ ...prev, [repoId]: value }));
  }, []);

  async function handleConnect() {
    if (!orgId) {
      setError("Could not determine your organization. Please refresh and try again.");
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const reposToConnect = repos.filter((r) => selected.has(r.github_repo_id));

      await Promise.all(
        reposToConnect.map((repo) => {
          const rawDir = rootDirs[repo.github_repo_id]?.trim() ?? "";
          return connectRepo({
            github_repo_id: repo.github_repo_id,
            github_full_name: repo.full_name,
            org_id: orgId,
            default_branch: repo.default_branch,
            installation_id: installationId,
            root_dir: rawDir || null,
          });
        }),
      );

      setSuccess(true);
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (err: any) {
      setError(err.message ?? "Failed to connect repositories");
    } finally {
      setIsConnecting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-14 rounded-xl border border-white/[0.06] bg-white/[0.02] animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (success) {
    return (
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-8 text-center">
        <p className="text-sm text-emerald-400 font-medium">
          Repositories connected successfully!
        </p>
        <p className="mt-1 text-xs text-white/40">
          Redirecting to dashboard...
        </p>
      </div>
    );
  }

  if (error && repos.length === 0) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      <div className="space-y-2">
        {repos.map((repo) => (
          <RepoRow
            key={repo.github_repo_id}
            repo={repo}
            installationId={installationId}
            isSelected={selected.has(repo.github_repo_id)}
            rootDir={rootDirs[repo.github_repo_id] ?? ""}
            onToggle={toggleRepo}
            onRootDirChange={setRootDir}
          />
        ))}
      </div>

      {repos.length === 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-8 text-center">
          <p className="text-sm text-white/40">
            No repositories found for this installation.
          </p>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <button
          onClick={handleConnect}
          disabled={selected.size === 0 || isConnecting}
          className="rounded-full bg-white text-black h-10 px-6 text-sm font-semibold transition-colors hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isConnecting
            ? "Connecting..."
            : `Connect ${selected.size} repo${selected.size !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  );
}
