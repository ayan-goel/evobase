/**
 * Typed API client for the Coreloop control plane.
 *
 * All functions throw on non-2xx responses.
 * Use NEXT_PUBLIC_API_URL to point at the FastAPI backend.
 */

import type {
  ConnectRepoRequest,
  GitHubRepo,
  Installation,
  Proposal,
  Repository,
  RepoSettings,
  Run,
} from "@/lib/types";
import { createClient } from "@/lib/supabase/client";

export interface LLMModel {
  id: string;
  label: string;
  description: string;
}

export interface LLMProvider {
  id: string;
  label: string;
  models: LLMModel[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  if (typeof window === "undefined") {
    try {
      const { createClient: createServerSupabase } = await import(
        "@/lib/supabase/server"
      );
      const supabase = await createServerSupabase();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.access_token) {
        return { Authorization: `Bearer ${session.access_token}` };
      }
    } catch {
      // No server session available
    }
    return {};
  }

  try {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
  } catch {
    // No session available
  }

  return {};
}

/** Shared fetch wrapper with error handling and automatic auth. */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const isServer = typeof window === "undefined";

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(init?.headers as Record<string, string> | undefined),
    },
    ...(isServer ? { cache: "no-store" as const } : {}),
  });

  if (res.status === 401 && !isServer) {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${path} — ${body}`);
  }

  return res.json() as Promise<T>;
}

/** List all repos accessible to the current user. */
export async function getRepos(): Promise<Repository[]> {
  const data = await apiFetch<{ repos: Repository[]; count: number }>("/repos");
  return data.repos;
}

/** Get a single repo by ID. */
export async function getRepo(repoId: string): Promise<Repository> {
  return apiFetch<Repository>(`/repos/${repoId}`);
}

/** List all runs for a repo (most recent first). */
export async function getRuns(repoId: string): Promise<Run[]> {
  const data = await apiFetch<{ runs: Run[] }>(`/repos/${repoId}/runs`);
  return data.runs;
}

/** List all proposals for a run. */
export async function getProposalsByRun(runId: string): Promise<Proposal[]> {
  const data = await apiFetch<{ proposals: Proposal[]; count: number }>(
    `/proposals/by-run/${runId}`,
  );
  return data.proposals;
}

/** Get a single proposal with full evidence. */
export async function getProposal(proposalId: string): Promise<Proposal> {
  return apiFetch<Proposal>(`/proposals/${proposalId}`);
}

/** Get a signed URL for an artifact download. */
export async function getArtifactSignedUrl(
  artifactId: string,
): Promise<{ signed_url: string; expires_in_seconds: number }> {
  return apiFetch(`/artifacts/${artifactId}/signed-url`);
}

/** Trigger a new optimization run for a repository. */
export async function triggerRun(repoId: string): Promise<Run> {
  return apiFetch<Run>(`/repos/${repoId}/run`, { method: "POST" });
}

/** Trigger PR creation for an accepted proposal. */
export async function createPR(
  repoId: string,
  proposalId: string,
): Promise<{ pr_url: string }> {
  return apiFetch(`/github/repos/${repoId}/proposals/${proposalId}/create-pr`, {
    method: "POST",
  });
}

/** Get settings for a repository. */
export async function getRepoSettings(repoId: string): Promise<RepoSettings> {
  return apiFetch<RepoSettings>(`/repos/${repoId}/settings`);
}

/** List available LLM models grouped by provider. */
export async function getLLMModels(): Promise<LLMProvider[]> {
  const data = await apiFetch<{ providers: LLMProvider[] }>("/llm/models");
  return data.providers;
}

/** Get the current user's IDs (user_id + org_id). */
export async function getMe(): Promise<{ user_id: string; org_id: string }> {
  return apiFetch<{ user_id: string; org_id: string }>("/auth/me");
}

/** List GitHub App installations for the current user. */
export async function getInstallations(): Promise<Installation[]> {
  const data = await apiFetch<{ installations: Installation[]; count: number }>(
    "/github/installations",
  );
  return data.installations;
}

/** List repos available via a GitHub App installation. */
export async function getInstallationRepos(
  installationId: number,
): Promise<GitHubRepo[]> {
  const data = await apiFetch<{ repos: GitHubRepo[]; count: number }>(
    `/github/installations/${installationId}/repos`,
  );
  return data.repos;
}

/** Link a GitHub App installation to the current user. */
export async function linkInstallation(
  installationId: number,
  accountLogin?: string,
  accountId?: number,
): Promise<{ installation_id: number; linked: boolean }> {
  return apiFetch("/github/link-installation", {
    method: "POST",
    body: JSON.stringify({
      installation_id: installationId,
      account_login: accountLogin,
      account_id: accountId,
    }),
  });
}

/** Connect a GitHub repo to Coreloop. */
export async function connectRepo(
  body: ConnectRepoRequest,
): Promise<Repository> {
  return apiFetch<Repository>("/repos/connect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Update settings for a repository (partial update). */
export async function updateRepoSettings(
  repoId: string,
  updates: Partial<Omit<RepoSettings, "repo_id" | "consecutive_setup_failures" | "consecutive_flaky_runs" | "last_run_at">>,
): Promise<RepoSettings> {
  return apiFetch<RepoSettings>(`/repos/${repoId}/settings`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}
