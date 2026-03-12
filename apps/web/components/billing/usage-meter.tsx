"use client";

interface UsageMeterProps {
  usagePct: number;
  periodEnd: string;
  overageActive?: boolean;
  className?: string;
}

export function UsageMeter({
  usagePct,
  periodEnd,
  overageActive = false,
  className = "",
}: UsageMeterProps) {
  const clampedPct = Math.min(usagePct, 100);
  const isWarning = usagePct >= 80 && usagePct < 100;
  const isDanger = usagePct >= 100;

  const barColor = isDanger
    ? "bg-red-500"
    : isWarning
      ? "bg-amber-500"
      : "bg-white/70";

  const resetDate = new Date(periodEnd).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className={className}>
      <div className="mb-1.5 flex items-center justify-between text-xs text-white/50">
        <span>
          {overageActive ? (
            <span className="text-amber-400">Pay-as-you-go active</span>
          ) : (
            `${Math.round(usagePct)}% of plan used`
          )}
        </span>
        <span>Resets {resetDate}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className={["h-full rounded-full transition-all duration-300", barColor].join(" ")}
          style={{ width: `${clampedPct}%` }}
          role="progressbar"
          aria-valuenow={Math.round(usagePct)}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
