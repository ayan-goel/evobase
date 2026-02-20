/**
 * Server-side API client for the Coreloop control plane.
 *
 * Import ONLY from Server Components and Route Handlers — never from
 * client components. Uses next/headers cookies via the Supabase server
 * client for authentication.
 */
import { createClient } from "@/lib/supabase/server";
import type {
  Installation,
  LLMProvider,
  Proposal,
  Repository,
  RepoSettings,
  Run,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const supabase = await createClient();
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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(init?.headers as Record<string, string> | undefined),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${path} — ${body}`);
  }

  return res.json() as Promise<T>;
}

export async function getRepos(): Promise<Repository[]> {
  const data = await apiFetch<{ repos: Repository[]; count: number }>("/repos");
  return data.repos;
}

export async function getRepo(repoId: string): Promise<Repository> {
  return apiFetch<Repository>(`/repos/${repoId}`);
}

export async function getRuns(repoId: string): Promise<Run[]> {
  const data = await apiFetch<{ runs: Run[] }>(`/repos/${repoId}/runs`);
  return data.runs;
}

export async function getProposalsByRun(runId: string): Promise<Proposal[]> {
  const data = await apiFetch<{ proposals: Proposal[]; count: number }>(
    `/proposals/by-run/${runId}`,
  );
  return data.proposals;
}

export async function getProposal(proposalId: string): Promise<Proposal> {
  return apiFetch<Proposal>(`/proposals/${proposalId}`);
}

export async function getArtifactSignedUrl(
  artifactId: string,
): Promise<{ signed_url: string; expires_in_seconds: number }> {
  return apiFetch(`/artifacts/${artifactId}/signed-url`);
}

export async function getRepoSettings(repoId: string): Promise<RepoSettings> {
  return apiFetch<RepoSettings>(`/repos/${repoId}/settings`);
}

export async function getLLMModels(): Promise<LLMProvider[]> {
  const data = await apiFetch<{ providers: LLMProvider[] }>("/llm/models");
  return data.providers;
}

export async function getMe(): Promise<{ user_id: string; org_id: string }> {
  return apiFetch<{ user_id: string; org_id: string }>("/auth/me");
}

export async function getInstallations(): Promise<Installation[]> {
  const data = await apiFetch<{ installations: Installation[]; count: number }>(
    "/github/installations",
  );
  return data.installations;
}
