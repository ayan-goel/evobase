"use client";

interface PlanOption {
  id: string;
  label: string;
  price: string | null;
}

const PLAN_OPTIONS: PlanOption[] = [
  { id: "free", label: "Free", price: null },
  { id: "hobby", label: "Hobby", price: "$20/mo" },
  { id: "premium", label: "Premium", price: "$60/mo" },
  { id: "pro", label: "Pro", price: "$200/mo" },
];

interface PlanSelectorProps {
  currentTier: string;
  onSelect: (tier: string) => void;
  disabled?: boolean;
}

export function PlanSelector({ currentTier, onSelect, disabled = false }: PlanSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {PLAN_OPTIONS.map((plan) => {
        const isSelected = plan.id === currentTier;
        return (
          <button
            key={plan.id}
            type="button"
            disabled={disabled || isSelected}
            onClick={() => onSelect(plan.id)}
            className={[
              "rounded-lg border px-4 py-2 text-sm transition-colors",
              isSelected
                ? "border-white/30 bg-white/[0.08] text-white font-medium cursor-default"
                : "border-white/10 bg-transparent text-white/70 hover:bg-white/[0.06] hover:text-white hover:border-white/20",
              disabled && !isSelected ? "opacity-50 cursor-not-allowed" : "",
            ].join(" ")}
          >
            <span className="font-medium">{plan.label}</span>
            {plan.price && (
              <span className="ml-1.5 text-white/40">{plan.price}</span>
            )}
            {isSelected && (
              <span className="ml-2 text-xs text-white/40">(current)</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
