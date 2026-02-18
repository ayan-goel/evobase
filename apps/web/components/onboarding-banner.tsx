import type { Run } from "@/lib/types";

interface OnboardingBannerProps {
  runs: Run[];
}

/**
 * Shown only when exactly one run exists and it is still queued or running —
 * i.e. the first baseline analysis triggered on repo connect.
 */
export function OnboardingBanner({ runs }: OnboardingBannerProps) {
  const isFirstRun =
    runs.length === 1 &&
    (runs[0].status === "queued" || runs[0].status === "running");

  if (!isFirstRun) return null;

  const isRunning = runs[0].status === "running";

  return (
    <div className="mb-8 rounded-xl border border-blue-500/20 bg-blue-500/5 p-6">
      <div className="flex items-start gap-4">
        <div className="mt-0.5 shrink-0">
          <span
            className={`inline-block h-2.5 w-2.5 rounded-full ${
              isRunning ? "bg-blue-400 animate-pulse" : "bg-blue-500/50"
            }`}
          />
        </div>
        <div>
          <p className="text-sm font-medium text-blue-300">
            Coreloop is analyzing your repository for the first time.
          </p>
          <p className="mt-1 text-xs text-white/40">
            This usually takes 2–5 minutes. You can leave this page — the run
            will continue in the background.
          </p>
        </div>
      </div>
    </div>
  );
}
