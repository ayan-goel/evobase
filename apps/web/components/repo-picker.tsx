"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  connectRepo,
  getInstallationRepos,
  getMe,
} from "@/lib/api";
import type { GitHubRepo } from "@/lib/types";

interface RepoPickerProps {
  installationId: number;
}

export function RepoPicker({ installationId }: RepoPickerProps) {
  const router = useRouter();
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
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

  function toggleRepo(repoId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(repoId)) {
        next.delete(repoId);
      } else {
        next.add(repoId);
      }
      return next;
    });
  }

  async function handleConnect() {
    if (!orgId) {
      setError("Could not determine your organization. Please refresh and try again.");
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const reposToConnect = repos.filter((r) => selected.has(r.github_repo_id));

      for (const repo of reposToConnect) {
        await connectRepo({
          github_repo_id: repo.github_repo_id,
          github_full_name: repo.full_name,
          org_id: orgId,
          default_branch: repo.default_branch,
          installation_id: installationId,
        });
      }

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
          <label
            key={repo.github_repo_id}
            className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 cursor-pointer hover:bg-white/[0.05] transition-colors"
          >
            <input
              type="checkbox"
              checked={selected.has(repo.github_repo_id)}
              onChange={() => toggleRepo(repo.github_repo_id)}
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
