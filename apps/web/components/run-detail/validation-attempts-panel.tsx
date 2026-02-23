export interface ValidationBenchmarkSummary {
  improvement_pct: number;
  passes_threshold: boolean;
  is_significant: boolean;
  baseline_duration_seconds: number;
  candidate_duration_seconds: number;
}

export interface ValidationAttemptVerdictSummary {
  is_accepted: boolean;
  confidence: string;
  reason: string;
  gates_passed: string[];
  gates_failed: string[];
  benchmark_comparison: ValidationBenchmarkSummary | null;
}

export interface ValidationStepSummary {
  name: string;
  command: string;
  exit_code: number;
  duration_seconds: number;
  stdout_lines: number;
  stderr_lines: number;
  is_success: boolean;
}

export interface ValidationAttemptSummary {
  attempt_number: number;
  patch_applied: boolean;
  error: string | null;
  timestamp: string;
  steps: ValidationStepSummary[];
  verdict: ValidationAttemptVerdictSummary | null;
}

interface ValidationAttemptsPanelProps {
  attempts: ValidationAttemptSummary[];
}

export function ValidationAttemptsPanel({ attempts }: ValidationAttemptsPanelProps) {
  if (!attempts.length) {
    return (
      <p className="text-xs text-white/30 italic">No validation attempt details captured.</p>
    );
  }

  return (
    <div className="space-y-2">
      {attempts.map((attempt) => (
        <div
          key={`${attempt.attempt_number}-${attempt.timestamp}`}
          className="rounded-md border border-white/[0.05] bg-white/[0.02] px-3 py-2"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-white/70">
              Attempt {attempt.attempt_number}
            </span>
            <span
              className={`text-[10px] rounded px-1.5 py-0.5 ${
                attempt.patch_applied
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "bg-red-500/10 text-red-300"
              }`}
            >
              {attempt.patch_applied ? "patch applied" : "patch not applied"}
            </span>
            <span className="text-[10px] text-white/20">
              {_fmtTime(attempt.timestamp)}
            </span>
          </div>

          {attempt.error ? (
            <p className="mt-1 text-xs text-red-300/70">{attempt.error}</p>
          ) : null}

          {attempt.steps.length > 0 ? (
            <div className="mt-2 space-y-1.5">
              {attempt.steps.map((step) => (
                <div
                  key={`${attempt.attempt_number}-${step.name}-${step.command}`}
                  className="rounded border border-white/[0.04] bg-black/10 px-2.5 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 flex items-center gap-2">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          step.is_success ? "bg-emerald-400" : "bg-red-400"
                        }`}
                        aria-hidden
                      />
                      <span className="text-xs text-white/70 font-mono">
                        {step.name}
                      </span>
                      <span className="text-[10px] text-white/30">
                        exit {step.exit_code}
                      </span>
                    </div>
                    <span className="text-[10px] text-white/35">
                      {step.duration_seconds.toFixed(2)}s
                    </span>
                  </div>
                  <p
                    className="mt-1 truncate text-[10px] text-white/35 font-mono"
                    title={step.command}
                  >
                    {step.command}
                  </p>
                  <p className="mt-0.5 text-[10px] text-white/25">
                    {step.stdout_lines} stdout lines · {step.stderr_lines} stderr lines
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          {attempt.verdict ? (
            <div className="mt-2 text-xs">
              <p className="text-white/40">{attempt.verdict.reason}</p>
              {(attempt.verdict.gates_failed ?? []).length > 0 ? (
                <p className="text-red-300/70 mt-0.5">
                  Failed: {(attempt.verdict.gates_failed ?? []).join(", ")}
                </p>
              ) : null}
              {(attempt.verdict.gates_passed ?? []).length > 0 ? (
                <p className="text-emerald-300/70 mt-0.5">
                  Passed: {(attempt.verdict.gates_passed ?? []).join(", ")}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function _fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}
