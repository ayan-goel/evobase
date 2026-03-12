"use client";

interface PlanBadgeProps {
  tier: string;
  className?: string;
}

const TIER_STYLES: Record<string, string> = {
  free: "bg-white/[0.06] text-white/60 border-white/10",
  hobby: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  premium: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  pro: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  enterprise: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

const TIER_LABELS: Record<string, string> = {
  free: "Free",
  hobby: "Hobby",
  premium: "Premium",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function PlanBadge({ tier, className = "" }: PlanBadgeProps) {
  const style = TIER_STYLES[tier] ?? TIER_STYLES.free;
  const label = TIER_LABELS[tier] ?? tier;

  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        style,
        className,
      ].join(" ")}
    >
      {label}
    </span>
  );
}
