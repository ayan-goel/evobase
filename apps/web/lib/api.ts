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
  LLMProvider,
  Proposal,
  RepoPatchRequest,
  Repository,
  RepoSettings,
  Run,
  RunCancelResult,
} from "@/lib/types";
import { createClient } from "@/lib/supabase/client";

export type { LLMModel, LLMProvider } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
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

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(init?.headers as Record<string, string> | undefined),
    },
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${path} — ${body}`);
  }

  // 204/205 are intentionally body-less (e.g. DELETE endpoints).
  if (res.status === 204 || res.status === 205) {
    return undefined as T;
  }

  // Prefer JSON when available, but tolerate empty or non-JSON bodies.
  const contentLength = res.headers?.get?.("content-length");
  if (contentLength === "0") {
    return undefined as T;
  }

  const contentType = res.headers?.get?.("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json() as Promise<T>;
  }

  // Some APIs return JSON without a content-type header.
  try {
    return await res.json() as T;
  } catch {
    const text = await res.text().catch(() => "");
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      return text as T;
    }
  }
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

/** Create a single GitHub PR for a run, combining the selected proposal diffs. */
export async function createRunPR(
  repoId: string,
  runId: string,
  proposalIds: string[],
): Promise<{ pr_url: string }> {
  return apiFetch(`/github/repos/${repoId}/runs/${runId}/create-pr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proposal_ids: proposalIds }),
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

/** Remove a repository from Coreloop (does not delete it from GitHub). */
export async function deleteRepo(repoId: string): Promise<void> {
  await apiFetch(`/repos/${repoId}`, { method: "DELETE" });
}

/** Update mutable repository config (root_dir and command overrides). */
export async function updateRepoConfig(
  repoId: string,
  updates: RepoPatchRequest,
): Promise<Repository> {
  return apiFetch<Repository>(`/repos/${repoId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export interface DetectFrameworkResult {
  framework: string | null;
  language: string | null;
  package_manager: string | null;
  confidence: number;
}

/** Detect the framework for a repository by probing its manifest files. */
export async function detectFramework(
  installationId: number,
  repoFullName: string,
  rootDir: string | null,
): Promise<DetectFrameworkResult> {
  return apiFetch<DetectFrameworkResult>("/repos/detect-framework", {
    method: "POST",
    body: JSON.stringify({
      installation_id: installationId,
      repo_full_name: repoFullName,
      root_dir: rootDir || null,
    }),
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

/** Fetch a single run by ID. */
export async function getRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/runs/${runId}`);
}

/** Permanently delete a run and all its associated data. */
export async function deleteRun(runId: string): Promise<void> {
  await apiFetch(`/runs/${runId}`, { method: "DELETE" });
}

/** Cancel a queued or running run. */
export async function cancelRun(runId: string): Promise<RunCancelResult> {
  return apiFetch<RunCancelResult>(`/runs/${runId}/cancel`, { method: "POST" });
}

/** Get the SSE events URL for a run (used by EventSource). */
export function getRunEventsUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/events`;
}
