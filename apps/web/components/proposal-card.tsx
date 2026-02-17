import Link from "next/link";
import { cn } from "@/lib/utils";
import { ConfidenceBadge } from "@/components/confidence-badge";
import type { Proposal } from "@/lib/types";

interface ProposalCardProps {
  proposal: Proposal;
  className?: string;
}

/** Displays a compact proposal summary with confidence, metrics delta, and link. */
export function ProposalCard({ proposal, className }: ProposalCardProps) {
  const testDelta = _testDurationDelta(proposal);
  const benchDelta = _benchDurationDelta(proposal);

  return (
    <Link
      href={`/proposals/${proposal.id}`}
      className={cn(
        "group block rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-5",
        "hover:bg-white/[0.05] hover:border-white/[0.10] transition-all",
        className,
      )}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-white leading-snug line-clamp-2">
          {proposal.summary ?? "Optimization proposal"}
        </p>
        <ConfidenceBadge confidence={proposal.confidence} className="shrink-0" />
      </div>

      {/* Metrics delta row */}
      {(testDelta !== null || benchDelta !== null) && (
        <div className="mt-3 flex flex-wrap gap-3">
          {testDelta !== null && (
            <MetricDelta label="Test time" delta={testDelta} unit="s" />
          )}
          {benchDelta !== null && (
            <MetricDelta label="Bench" delta={benchDelta} unit="s" />
          )}
        </div>
      )}

      {/* Footer row */}
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {proposal.risk_score !== null && (
            <span className="text-xs text-white/40">
              Risk {Math.round(proposal.risk_score * 100)}%
            </span>
          )}
          <span className="text-xs text-white/40">
            {_formatRelative(proposal.created_at)}
          </span>
        </div>

        {proposal.pr_url ? (
          <span className="text-xs text-emerald-400 font-medium">PR created</span>
        ) : (
          <span className="text-xs text-white/30 group-hover:text-white/50 transition-colors">
            View →
          </span>
        )}
      </div>
    </Link>
  );
}

/** Shows a before→after metric delta with green/red colouring. */
function MetricDelta({
  label,
  delta,
  unit,
}: {
  label: string;
  delta: number;
  unit: string;
}) {
  // delta is negative = improvement (faster), positive = regression
  const improved = delta < 0;
  const sign = improved ? "−" : "+";
  const abs = Math.abs(delta).toFixed(2);

  return (
    <span
      className={cn(
        "text-xs font-medium rounded-full px-2 py-0.5 border",
        improved
          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
          : "bg-red-500/10 text-red-300 border-red-500/20",
      )}
    >
      {label}: {sign}{abs}{unit}
    </span>
  );
}

function _testDurationDelta(proposal: Proposal): number | null {
  const before = _findStepDuration(proposal.metrics_before, "test");
  const after = _findStepDuration(proposal.metrics_after, "test");
  if (before === null || after === null) return null;
  return after - before;
}

function _benchDurationDelta(proposal: Proposal): number | null {
  const before = proposal.metrics_before?.bench_result?.duration_seconds ?? null;
  const after = proposal.metrics_after?.bench_result?.duration_seconds ?? null;
  if (before === null || after === null) return null;
  return (after as number) - (before as number);
}

function _findStepDuration(
  metrics: Proposal["metrics_before"],
  stepName: string,
): number | null {
  if (!metrics?.steps) return null;
  const step = (metrics.steps as Array<{ name: string; duration_seconds: number }>).find(
    (s) => s.name === stepName,
  );
  return step?.duration_seconds ?? null;
}

function _formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
