"use client";

import { useState } from "react";
import { triggerRun } from "@/lib/api";

interface TriggerRunButtonProps {
  repoId: string;
  /** Called after a run is successfully queued, with the new run id. */
  onQueued?: (runId: string) => void;
}

type State = "idle" | "loading" | "queued" | "error";

export function TriggerRunButton({ repoId, onQueued }: TriggerRunButtonProps) {
  const [state, setState] = useState<State>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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

  if (state === "queued") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-400">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Queued
      </span>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleClick}
        disabled={state === "loading"}
        className="rounded-full border border-white/15 bg-white/8 px-4 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/14 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
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
