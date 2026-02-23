"use client";

import type { RunPhase } from "@/lib/types";

interface PhaseProgressProps {
  currentPhase: RunPhase | null;
  isDone: boolean;
}

const PHASES: { key: RunPhase; label: string }[] = [
  { key: "clone", label: "Clone" },
  { key: "detection", label: "Detect" },
  { key: "baseline", label: "Baseline" },
  { key: "discovery", label: "Discover" },
  { key: "validation", label: "Validate" },
  { key: "run", label: "Done" },
];

const PHASE_INDEX: Record<string, number> = {};
PHASES.forEach((p, i) => {
  PHASE_INDEX[p.key] = i;
});

function resolveIndex(phase: RunPhase | null): number {
  if (!phase) return -1;
  if (phase === "patching" || phase === "selection") return PHASE_INDEX["validation"] ?? -1;
  return PHASE_INDEX[phase] ?? -1;
}

export function PhaseProgress({ currentPhase, isDone }: PhaseProgressProps) {
  const activeIdx = isDone ? PHASES.length : resolveIndex(currentPhase);

  return (
    <div className="flex items-center gap-1">
      {PHASES.map((phase, idx) => {
        const isComplete = isDone || idx < activeIdx;
        const isActive = !isDone && idx === activeIdx;

        return (
          <div key={phase.key} className="flex items-center gap-1 flex-1">
            <div className="flex flex-col items-center flex-1">
              <div
                className={`
                  h-1.5 w-full rounded-full transition-all duration-500
                  ${isComplete
                    ? "bg-emerald-500/70"
                    : isActive
                      ? "bg-blue-500/70 animate-pulse"
                      : "bg-white/[0.08]"
                  }
                `}
              />
              <span
                className={`
                  mt-1.5 text-[10px] font-medium tracking-wide uppercase
                  ${isComplete
                    ? "text-emerald-400/70"
                    : isActive
                      ? "text-blue-400/80"
                      : "text-white/20"
                  }
                `}
              >
                {phase.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
