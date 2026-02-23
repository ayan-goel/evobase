"use client";

import { cn } from "@/lib/utils";
import type { Proposal } from "@/lib/types";

interface ProposalCardProps {
  proposal: Proposal;
  onSelect?: () => void;
  className?: string;
}

/** Compact proposal card — click fires onSelect to open the detail drawer. */
export function ProposalCard({ proposal, onSelect, className }: ProposalCardProps) {
  const testDelta = _testDurationDelta(proposal);
  const benchDelta = _benchDurationDelta(proposal);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect?.(); }}
      className={cn(
        "group cursor-pointer rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-5",
        "hover:bg-white/[0.05] hover:border-white/[0.10] transition-all select-none",
        className,
      )}
    >
      {/* Summary */}
      <p className="text-sm font-medium text-white leading-snug line-clamp-2">
        {proposal.summary ?? "Optimization proposal"}
      </p>

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
        <span suppressHydrationWarning className="text-xs text-white/40">
          {_formatRelative(proposal.created_at)}
        </span>

        {proposal.pr_url ? (
          <span className="text-xs text-emerald-400 font-medium">PR created</span>
        ) : (
          <span className="text-xs text-white/30 group-hover:text-white/50 transition-colors">
            View →
          </span>
        )}
      </div>
    </div>
  );
}

function MetricDelta({
  label,
  delta,
  unit,
}: {
  label: string;
  delta: number;
  unit: string;
}) {
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
