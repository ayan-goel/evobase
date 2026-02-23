"use client";

/**
 * PatchVariants — displays all approach variants the agent tried for one proposal.
 *
 * The winning variant is shown first and expanded by default. Each tab shows:
 *   - The approach strategy description
 *   - Pass/fail badge and confidence level
 *   - Metrics after applying the patch
 *   - Collapsible diff viewer
 *   - Collapsible agent reasoning (patch_trace)
 *   - Gates passed / failed
 */

import { useState } from "react";
import { cn } from "@/lib/utils";
import { DiffViewer } from "@/components/diff-viewer";
import { PatchReasoningPanel } from "@/components/patch-reasoning-panel";
import type { Metrics, PatchVariant } from "@/lib/types";

interface PatchVariantsProps {
  variants: PatchVariant[];
  className?: string;
}

export function PatchVariants({ variants, className }: PatchVariantsProps) {
  // Sort: selected variant first, then by approach_index
  const sorted = [...variants].sort((a, b) => {
    if (a.is_selected !== b.is_selected) return a.is_selected ? -1 : 1;
    return a.approach_index - b.approach_index;
  });

  const [activeIdx, setActiveIdx] = useState(0);

  if (sorted.length === 0) return null;

  const active = sorted[activeIdx];

  return (
    <div className={cn("rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden", className)}>
      {/* Tab bar */}
      <div className="flex gap-0 border-b border-white/[0.06] overflow-x-auto">
        {sorted.map((v, i) => (
          <button
            key={v.approach_index}
            onClick={() => setActiveIdx(i)}
            className={cn(
              "flex-shrink-0 flex items-center gap-2 px-4 py-3 text-xs font-medium transition-colors",
              activeIdx === i
                ? "text-white border-b-2 border-white/40 bg-white/[0.03]"
                : "text-white/40 hover:text-white/60",
            )}
          >
            <span
              className={cn(
                "inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-semibold border",
                _statusColors(v),
              )}
            >
              {v.is_selected ? "✓" : "✗"}
            </span>
            <span>
              Approach {v.approach_index + 1}
              {v.is_selected && (
                <span className="ml-1.5 text-[10px] text-white/30">(chosen)</span>
              )}
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-5 space-y-5">
        <VariantContent variant={active} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Variant content
// ---------------------------------------------------------------------------

function VariantContent({ variant }: { variant: PatchVariant }) {
  const [diffOpen, setDiffOpen] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);

  const verdict = variant.validation_result;

  return (
    <div className="space-y-4">
      {/* Strategy description */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-white/40 mb-1">
          Strategy
        </p>
        <p className="text-sm text-white/80 leading-relaxed">
          {variant.approach_description || "No description available"}
        </p>
      </div>

      {/* Status row */}
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge variant={variant} />
        {verdict?.confidence && (
          <span className={cn(
            "rounded-full border px-2.5 py-0.5 text-xs font-medium",
            _confidenceColors(verdict.confidence),
          )}>
            {_confidenceLabel(verdict.confidence)}
          </span>
        )}
        {verdict?.benchmark_comparison?.is_significant && (
          <span className={cn(
            "rounded-full border px-2.5 py-0.5 text-xs font-medium",
            verdict.benchmark_comparison.improvement_pct >= 0
              ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
              : "bg-red-500/10 text-red-300 border-red-500/20",
          )}>
            {verdict.benchmark_comparison.improvement_pct >= 0 ? "+" : ""}
            {verdict.benchmark_comparison.improvement_pct.toFixed(1)}% bench
          </span>
        )}
      </div>

      {/* Selection reason (winner only) */}
      {variant.is_selected && variant.selection_reason && (
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 py-2.5">
          <p className="text-xs text-white/40 mb-0.5 font-medium uppercase tracking-wider">
            Why chosen
          </p>
          <p className="text-xs text-white/65">{variant.selection_reason}</p>
        </div>
      )}

      {/* Gates */}
      {verdict && (verdict.gates_passed.length > 0 || verdict.gates_failed.length > 0) && (
        <GatesList passed={verdict.gates_passed} failed={verdict.gates_failed} />
      )}

      {/* Rejection reason (non-winners) */}
      {!variant.is_selected && verdict?.reason && (
        <div className="rounded-lg border border-red-500/10 bg-red-500/[0.04] px-3.5 py-2.5">
          <p className="text-xs text-white/40 mb-0.5 font-medium uppercase tracking-wider">
            Why rejected
          </p>
          <p className="text-xs text-red-300/70">{verdict.reason}</p>
        </div>
      )}

      {/* Metrics after */}
      {variant.metrics_after && (
        <MetricsCard metrics={variant.metrics_after} />
      )}

      {/* Diff (collapsible) */}
      {variant.diff && (
        <Collapsible
          label="View diff"
          open={diffOpen}
          onToggle={() => setDiffOpen((v) => !v)}
        >
          <DiffViewer diff={variant.diff} />
        </Collapsible>
      )}

      {/* Patch reasoning (collapsible) */}
      {variant.patch_trace && (
        <Collapsible
          label="Patch generation reasoning"
          open={reasoningOpen}
          onToggle={() => setReasoningOpen((v) => !v)}
        >
          <PatchReasoningPanel trace={variant.patch_trace} />
        </Collapsible>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ variant }: { variant: PatchVariant }) {
  const accepted = variant.validation_result?.is_accepted ?? false;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        accepted
          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
          : "bg-red-500/10 text-red-300 border-red-500/20",
      )}
    >
      <span>{accepted ? "✓" : "✗"}</span>
      {accepted ? "Validation passed" : "Validation failed"}
    </span>
  );
}

function GatesList({ passed, failed }: { passed: string[]; failed: string[] }) {
  return (
    <div className="space-y-1.5">
      {failed.map((g) => (
        <div key={g} className="flex items-center gap-2 text-xs">
          <span className="text-red-400">✗</span>
          <span className="text-white/50 font-mono">{g}</span>
        </div>
      ))}
      {passed.map((g) => (
        <div key={g} className="flex items-center gap-2 text-xs">
          <span className="text-emerald-400">✓</span>
          <span className="text-white/50 font-mono">{g}</span>
        </div>
      ))}
    </div>
  );
}

function MetricsCard({ metrics }: { metrics: Metrics }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
      <p className="text-xs font-medium text-white/40 mb-3">Metrics after patch</p>
      <div className="space-y-1.5">
        {metrics.steps.map((step) => (
          <div key={step.name} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-white/60 font-mono">
              <span className={step.is_success ? "text-emerald-400" : "text-red-400"}>
                {step.is_success ? "✓" : "✗"}
              </span>
              {step.name}
            </span>
            <span className="text-white/40">{step.duration_seconds.toFixed(2)}s</span>
          </div>
        ))}
        {metrics.bench_result && (
          <div className="flex items-center justify-between text-xs pt-1 border-t border-white/[0.04]">
            <span className="text-white/50 font-mono">bench</span>
            <span className="text-white/40">
              {metrics.bench_result.duration_seconds.toFixed(3)}s
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function Collapsible({
  label,
  open,
  onToggle,
  children,
}: {
  label: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/[0.06]">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-xs font-medium text-white/50 hover:text-white/70 transition-colors"
        aria-expanded={open}
      >
        <span>{label}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          className={cn("text-white/30 transition-transform duration-200", open && "rotate-180")}
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <div className="border-t border-white/[0.04] p-4">
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _statusColors(variant: PatchVariant): string {
  if (variant.is_selected)
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400";
  if (variant.validation_result?.is_accepted)
    return "border-emerald-500/20 bg-emerald-500/5 text-emerald-500/60";
  return "border-red-500/20 bg-red-500/5 text-red-400/60";
}

function _confidenceColors(confidence: string): string {
  if (confidence === "high") return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (confidence === "medium") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-orange-500/10 text-orange-300 border-orange-500/20";
}

function _confidenceLabel(confidence: string): string {
  if (confidence === "high") return "High confidence";
  if (confidence === "medium") return "Medium confidence";
  return "Low confidence";
}
