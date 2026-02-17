import { cn } from "@/lib/utils";
import type { RunStatus } from "@/lib/types";

interface RunStatusBadgeProps {
  status: RunStatus;
  className?: string;
}

const STATUS_STYLES: Record<RunStatus, string> = {
  queued: "bg-white/[0.06] text-white/60 border-white/[0.10]",
  running: "bg-blue-500/10 text-blue-300 border-blue-500/20",
  completed: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  failed: "bg-red-500/10 text-red-300 border-red-500/20",
};

const STATUS_DOTS: Record<RunStatus, string> = {
  queued: "bg-white/40",
  running: "bg-blue-400 animate-pulse",
  completed: "bg-emerald-400",
  failed: "bg-red-400",
};

/** Pill badge showing a run's current status. */
export function RunStatusBadge({ status, className }: RunStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        STATUS_STYLES[status],
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", STATUS_DOTS[status])} />
      {status}
    </span>
  );
}
