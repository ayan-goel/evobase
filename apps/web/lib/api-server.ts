/**
 * Server-side API client for the Evobase control plane.
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
  return res.json() as Promise<T>;
}

export const getRepos = cache(async (): Promise<Repository[]> => {
  const data = await apiFetch<{ repos: Repository[]; count: number }>("/repos");
  return data.repos;
});

export const getRepo = cache(async (repoId: string): Promise<Repository> => {
  return apiFetch<Repository>(`/repos/${repoId}`);
});

export const getRuns = cache(async (repoId: string): Promise<Run[]> => {
  const data = await apiFetch<{ runs: Run[] }>(`/repos/${repoId}/runs`);
  return data.runs;
});

export const getProposalsByRun = cache(async (runId: string): Promise<Proposal[]> => {
  const data = await apiFetch<{ proposals: Proposal[]; count: number }>(
    `/proposals/by-run/${runId}`,
  );
  return data.proposals;
});

export const getProposal = cache(async (proposalId: string): Promise<Proposal> => {
  return apiFetch<Proposal>(`/proposals/${proposalId}`);
});

export const getArtifactSignedUrl = cache(async (
  artifactId: string,
): Promise<{ signed_url: string; expires_in_seconds: number }> => {
  return apiFetch(`/artifacts/${artifactId}/signed-url`);
});

export const getRun = cache(async (runId: string): Promise<Run> => {
  return apiFetch<Run>(`/runs/${runId}`);
});

export const getRepoSettings = cache(async (repoId: string): Promise<RepoSettings> => {
  return apiFetch<RepoSettings>(`/repos/${repoId}/settings`);
});

export const getLLMModels = cache(async (): Promise<LLMProvider[]> => {
  const data = await apiFetch<{ providers: LLMProvider[] }>("/llm/models");
  return data.providers;
});

export const getMe = cache(async (): Promise<{ user_id: string; org_id: string }> => {
  return apiFetch<{ user_id: string; org_id: string }>("/auth/me");
});

export const getInstallations = cache(async (): Promise<Installation[]> => {
  const data = await apiFetch<{ installations: Installation[]; count: number }>(
    "/github/installations",
  );
  return data.installations;
});

export interface BillingSubscription {
  tier: string;
  current_period_start: string;
  current_period_end: string;
  usage_pct: number;
  overage_active: boolean;
  monthly_spend_limit_microdollars: number | null;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export interface UsageRunRow {
  run_id: string;
  created_at: string;
  api_cost_microdollars: number;
  billed_microdollars: number;
  call_count: number;
}

export interface BillingUsage {
  period_start: string;
  period_end: string;
  total_api_cost_microdollars: number;
  total_billed_microdollars: number;
  included_api_budget_microdollars: number;
  usage_pct: number;
  runs: UsageRunRow[];
  runs: UsageRunRow[];
}

export const getBillingSubscription = cache(async (): Promise<BillingSubscription> => {
  return apiFetch<BillingSubscription>("/billing/subscription");
});

export const getBillingUsage = cache(async (): Promise<BillingUsage> => {
  return apiFetch<BillingUsage>("/billing/usage");
});
