/** Shared TypeScript interfaces mirroring the API response schemas. */

export interface Repository {
  id: string;
  github_repo_id: number | null;
  github_full_name: string | null;
  default_branch: string;
  package_manager: string | null;
  install_cmd: string | null;
  build_cmd: string | null;
  test_cmd: string | null;
  typecheck_cmd: string | null;
  created_at: string;
}

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface Run {
  id: string;
  repo_id: string;
  sha: string | null;
  status: RunStatus;
  created_at: string;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export interface Artifact {
  id: string;
  proposal_id: string;
  storage_path: string;
  type: string;
  created_at: string;
}

export interface StepMetric {
  name: string;
  exit_code: number;
  duration_seconds: number;
  is_success: boolean;
}

export interface Metrics {
  is_success: boolean;
  total_duration_seconds: number;
  step_count: number;
  steps: StepMetric[];
  bench_result?: { duration_seconds: number; command: string } | null;
  error?: string | null;
}

export interface Proposal {
  id: string;
  run_id: string;
  diff: string;
  summary: string | null;
  metrics_before: Metrics | null;
  metrics_after: Metrics | null;
  risk_score: number | null;
  confidence: ConfidenceLevel | null;
  created_at: string;
  pr_url: string | null;
  artifacts: Artifact[];
}

export interface ThinkingTrace {
  model: string;
  provider: string;
  reasoning: string;
  prompt_tokens: number;
  completion_tokens: number;
  tokens_used: number;
  timestamp: string;
}

export interface RepoSettings {
  repo_id: string;
  compute_budget_minutes: number;
  max_proposals_per_run: number;
  max_candidates_per_run: number;
  schedule: string;
  paused: boolean;
  consecutive_setup_failures: number;
  consecutive_flaky_runs: number;
  last_run_at: string | null;
}

export interface TraceAttempt {
  attempt_number: number;
  patch_applied: boolean;
  timestamp: string;
  error: string | null;
  steps: StepMetric[];
  llm_reasoning: ThinkingTrace | null;
  verdict: {
    is_accepted: boolean;
    confidence: ConfidenceLevel;
    reason: string;
    gates_passed: string[];
    gates_failed: string[];
  } | null;
}
