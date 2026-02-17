import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/lib/types";

interface ConfidenceBadgeProps {
  confidence: ConfidenceLevel | null;
  className?: string;
}

const CONFIDENCE_STYLES: Record<ConfidenceLevel, string> = {
  high: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  medium: "bg-amber-500/10 text-amber-300 border-amber-500/20",
  low: "bg-orange-500/10 text-orange-300 border-orange-500/20",
};

const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence — review required",
};

/** Pill badge showing the acceptance confidence level for a proposal. */
export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  if (!confidence) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        CONFIDENCE_STYLES[confidence],
        className,
      )}
    >
      {CONFIDENCE_LABELS[confidence]}
    </span>
  );
}
