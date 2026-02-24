/** Shared TypeScript interfaces mirroring the API response schemas. */

export interface Repository {
  id: string;
  github_repo_id: number | null;
  github_full_name: string | null;
  default_branch: string;
  installation_id?: number | null;
  package_manager: string | null;
  framework: string | null;
  install_cmd: string | null;
  build_cmd: string | null;
  test_cmd: string | null;
  typecheck_cmd: string | null;
  root_dir: string | null;
  latest_run_status?: string | null;
  latest_failure_step?: string | null;
  setup_failing: boolean;
  created_at: string;
}

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface Run {
  id: string;
  repo_id: string;
  sha: string | null;
  status: RunStatus;
  compute_minutes: number | null;
  /** First pipeline step that failed: "install" | "build" | "test" | "unknown" */
  failure_step: string | null;
  /** Subject line of the HEAD commit, shown next to the SHA in the run header */
  commit_message: string | null;
  /** GitHub PR URL once a run-level PR has been created */
  pr_url?: string | null;
  created_at: string;
}

export type ConfidenceLevel = "high" | "medium" | "low";

export interface Artifact {
  id: string;
  // Null for baseline artifacts (run-level), set for proposal-level artifacts
  proposal_id: string | null;
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

export interface PatchVariantValidation {
  is_accepted: boolean;
  confidence: string;
  reason: string;
  gates_passed: string[];
  gates_failed: string[];
  benchmark_comparison: {
    improvement_pct: number;
    passes_threshold: boolean;
    is_significant: boolean;
    baseline_duration_seconds: number;
    candidate_duration_seconds: number;
  } | null;
}

export interface PatchVariant {
  approach_index: number;
  approach_description: string;
  diff: string;
  is_selected: boolean;
  selection_reason: string;
  metrics_after: Metrics | null;
  patch_trace: ThinkingTrace | null;
  validation_result: PatchVariantValidation | null;
}

export interface Proposal {
  id: string;
  run_id: string;
  repo_id: string;
  diff: string;
  title?: string | null;
  summary: string | null;
  metrics_before: Metrics | null;
  metrics_after: Metrics | null;
  risk_score: number | null;
  confidence: ConfidenceLevel | null;
  created_at: string;
  pr_url: string | null;
  framework: string | null;
  patch_variants: PatchVariant[];
  selection_reason: string | null;
  approaches_tried: number | null;
  artifacts: Artifact[];
  discovery_trace: ThinkingTrace | null;
  patch_trace: ThinkingTrace | null;
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
  max_prs_per_day: number;
  max_proposals_per_run: number;
  max_candidates_per_run: number;
  schedule: string;
  paused: boolean;
  consecutive_setup_failures: number;
  consecutive_flaky_runs: number;
  last_run_at: string | null;
  llm_provider: string;
  llm_model: string;
  execution_mode: "strict" | "adaptive";
  max_strategy_attempts: number;
}

export interface Installation {
  id: string;
  installation_id: number;
  account_login: string;
  account_id: number;
}

export interface GitHubRepo {
  github_repo_id: number;
  full_name: string;
  name: string;
  default_branch: string;
  private: boolean;
}

export interface ConnectRepoRequest {
  github_repo_id: number;
  github_full_name: string;
  org_id: string;
  default_branch: string;
  installation_id: number;
  root_dir?: string | null;
}

export interface RepoPatchRequest {
  root_dir?: string | null;
  install_cmd?: string | null;
  build_cmd?: string | null;
  test_cmd?: string | null;
  typecheck_cmd?: string | null;
}

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

// ---------------------------------------------------------------------------
// Run event streaming types
// ---------------------------------------------------------------------------

export type RunPhase =
  | "clone"
  | "detection"
  | "baseline"
  | "discovery"
  | "patching"
  | "validation"
  | "selection"
  | "run";

export type RunEventType =
  | "clone.started"
  | "clone.completed"
  | "detection.completed"
  | "baseline.attempt.started"
  | "baseline.step.completed"
  | "baseline.completed"
  | "discovery.started"
  | "discovery.files.selected"
  | "discovery.file.analysing"
  | "discovery.file.analysed"
  | "discovery.opportunity.found"
  | "discovery.completed"
  | "patch.started"
  | "patch.approach.started"
  | "patch.approach.completed"
  | "patch.completed"
  | "patch.failed"
  | "validation.started"
  | "validation.candidate.started"
  | "validation.step.completed"
  | "validation.verdict"
  | "selection.completed"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "heartbeat";

export interface RunEvent {
  id: string;
  type: RunEventType;
  phase: RunPhase;
  ts: string;
  data: Record<string, unknown>;
}

export interface RunCancelResult {
  run_id: string;
  status: string;
  cancelled: boolean;
}
