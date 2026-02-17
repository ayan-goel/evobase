/**
 * Typed API client for the SelfOpt control plane.
 *
 * All functions throw on non-2xx responses.
 * Use NEXT_PUBLIC_API_URL to point at the FastAPI backend.
 */

import type { Proposal, Repository, RepoSettings, Run } from "@/lib/types";

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

/** Shared fetch wrapper with error handling. */
async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${path} — ${body}`);
  }

  return res.json() as Promise<T>;
}

/** List all repos accessible to the current user. */
export async function getRepos(): Promise<Repository[]> {
  return apiFetch<Repository[]>("/repos");
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
