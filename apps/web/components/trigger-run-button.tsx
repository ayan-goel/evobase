"use client";

import { useEffect, useState } from "react";
import { triggerRun } from "@/lib/api";
import type { RunStatus } from "@/lib/types";

interface TriggerRunButtonProps {
  repoId: string;
  /** Called after a run is successfully queued, with the new run id. */
  onQueued?: (runId: string) => void;
  /** Live status from the current active run, if any. */
  activeStatus?: RunStatus | null;
}

type State = "idle" | "loading" | "queued" | "error";

export function TriggerRunButton({ repoId, onQueued, activeStatus }: TriggerRunButtonProps) {
  const [state, setState] = useState<State>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // When parent polling confirms there is no active run anymore, clear the
  // local queued state so the action button reappears.
  useEffect(() => {
    if (activeStatus === null && state === "queued") {
      setState("idle");
    }
  }, [activeStatus, state]);

  async function handleClick() {
    setState("loading");
    setErrorMsg(null);
    try {
      const run = await triggerRun(repoId);
      setState("queued");
      onQueued?.(run.id);
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to trigger run.");
    }
  }

  const displayStatus =
    activeStatus === "queued" || activeStatus === "running"
      ? activeStatus
      : state === "queued"
        ? "queued"
        : null;

  if (displayStatus) {
    const isRunning = displayStatus === "running";
    return (
      <span
        className={
          isRunning
            ? "inline-flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-xs font-medium text-blue-300"
            : "inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-400"
        }
      >
        <span
          className={
            isRunning
              ? "h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse"
              : "h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"
          }
        />
        {isRunning ? "Running" : "Queued"}
      </span>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleClick}
        disabled={state === "loading"}
        className="rounded-lg border border-white/15 bg-white/[0.05] px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {state === "loading" ? (
          <span className="inline-flex items-center gap-2">
            <span className="h-3 w-3 rounded-full border border-white/40 border-t-white/80 animate-spin" />
            Triggering…
          </span>
        ) : (
          "Trigger Run"
        )}
      </button>
      {state === "error" && errorMsg && (
        <p className="text-xs text-red-400">{errorMsg}</p>
      )}
    </div>
  );
}
