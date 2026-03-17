"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  connectRepo,
  getInstallationRepos,
  getMe,
} from "@/lib/api";
import type { GitHubRepo } from "@/lib/types";
import { useDetectFramework } from "@/hooks/use-detect-framework";
import { FrameworkBadge } from "@/components/framework-badge";

interface ConnectionEntry {
  id: string;
  repoId: number;
  rootDir: string;
}

interface RepoPickerProps {
  installationId: number;
}

interface RepoRowProps {
  repo: GitHubRepo;
  installationId: number;
  entries: ConnectionEntry[];
  onToggle: () => void;
  onAddDir: () => void;
  onRemoveDir: (id: string) => void;
  onDirChange: (id: string, value: string) => void;
}

interface DirSlotProps {
  entry: ConnectionEntry;
  repo: GitHubRepo;
  installationId: number;
  canRemove: boolean;
  onRemove: () => void;
  onChange: (value: string) => void;
}

function DirSlot({
  entry,
  repo,
  installationId,
  canRemove,
  onRemove,
  onChange,
}: DirSlotProps) {
  const { result, isDetecting } = useDetectFramework(
    installationId,
    repo.full_name,
    entry.rootDir,
  );

  return (
    <div className="mt-2">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={entry.rootDir}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. apps/web, packages/backend"
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
        />
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="flex items-center justify-center h-6 w-6 rounded text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors shrink-0"
            aria-label="Remove directory"
          >
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
              <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>
      <div className="mt-1 h-5 flex items-center">
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
  );
}

function RepoRow({
  repo,
  installationId,
  entries,
  onToggle,
  onAddDir,
  onRemoveDir,
  onDirChange,
}: RepoRowProps) {
  const isSelected = entries.length > 0;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 transition-colors hover:bg-white/[0.05]">
      <div
        className="flex items-center gap-3 cursor-pointer select-none"
        onClick={onToggle}
      >
        <div
          className={`h-4 w-4 rounded flex items-center justify-center shrink-0 border transition-colors ${
            isSelected ? "bg-white border-white" : "bg-white/5 border-white/20"
          }`}
        >
          {isSelected && (
            <svg className="h-2.5 w-2.5 text-black" viewBox="0 0 10 8" fill="none">
              <path
                d="M1 4l3 3 5-6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {repo.full_name}
          </p>
          <p className="text-xs text-white/40">
            {repo.default_branch}
            {repo.private && " · private"}
          </p>
        </div>
      </div>

      {isSelected && (
        <div className="mt-3 pl-7">
          <p className="text-xs text-white/40 mb-2">
            Project directory{" "}
            <span className="text-white/25">(optional — leave blank for repo root)</span>
          </p>

          {entries.map((entry) => (
            <DirSlot
              key={entry.id}
              entry={entry}
              repo={repo}
              installationId={installationId}
              canRemove={entries.length > 1}
              onRemove={() => onRemoveDir(entry.id)}
              onChange={(value) => onDirChange(entry.id, value)}
            />
          ))}

          <p className="mt-2 text-xs text-white/25">
            For monorepos: specify the sub-project folder that contains{" "}
            <code className="text-white/35">package.json</code> or{" "}
            <code className="text-white/35">pyproject.toml</code>.
          </p>

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAddDir();
            }}
            className="mt-2 text-xs text-white/35 hover:text-white/60 transition-colors"
          >
            + Add another directory
          </button>
        </div>
      )}
    </div>
  );
}

export function RepoPicker({ installationId }: RepoPickerProps) {
  const router = useRouter();
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [connections, setConnections] = useState<ConnectionEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(null);

  const connectionsByRepo = useMemo(() => {
    const map = new Map<number, ConnectionEntry[]>();
    for (const c of connections) {
      const list = map.get(c.repoId) ?? [];
      list.push(c);
      map.set(c.repoId, list);
    }
    return map;
  }, [connections]);

  useEffect(() => {
    async function load() {
      try {
        const [repoList, me] = await Promise.all([
          getInstallationRepos(installationId),
          getMe(),
        ]);
        setRepos(repoList);
        setOrgId(me.org_id);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to load repositories";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [installationId]);

  function toggleRepo(repoId: number) {
    setConnections((prev) => {
      const hasRepo = prev.some((c) => c.repoId === repoId);
      if (hasRepo) return prev.filter((c) => c.repoId !== repoId);
      return [...prev, { id: crypto.randomUUID(), repoId, rootDir: "" }];
    });
  }

  function addDir(repoId: number) {
    setConnections((prev) => [
      ...prev,
      { id: crypto.randomUUID(), repoId, rootDir: "" },
    ]);
  }

  function removeDir(id: string) {
    setConnections((prev) => prev.filter((c) => c.id !== id));
  }

  function updateDir(id: string, rootDir: string) {
    setConnections((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rootDir } : c)),
    );
  }

  async function handleConnect() {
    if (!orgId) {
      setError("Could not determine your organization. Please refresh and try again.");
      return;
    }

    setIsConnecting(true);
    setError(null);

    const repoMap = new Map(repos.map((r) => [r.github_repo_id, r]));

    try {
      await Promise.all(
        connections.map((conn) => {
          const repo = repoMap.get(conn.repoId);
          if (!repo) return undefined;
          const rawDir = conn.rootDir.trim();
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
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to connect repositories";
      setError(message);
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
        <p className="mt-1 text-xs text-white/40">Redirecting to dashboard...</p>
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
            entries={connectionsByRepo.get(repo.github_repo_id) ?? []}
            onToggle={() => toggleRepo(repo.github_repo_id)}
            onAddDir={() => addDir(repo.github_repo_id)}
            onRemoveDir={removeDir}
            onDirChange={updateDir}
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
          disabled={connections.length === 0 || isConnecting}
          className="rounded-full bg-white text-black h-10 px-6 text-sm font-semibold transition-colors hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isConnecting
            ? "Connecting..."
            : `Connect ${connections.length} project${connections.length !== 1 ? "s" : ""}`}
        </button>
      </div>
    </div>
  );
}
