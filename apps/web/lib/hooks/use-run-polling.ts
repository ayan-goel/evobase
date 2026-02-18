"use client";

import { useEffect, useState } from "react";
import { getRuns } from "@/lib/api";
import type { Run } from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

function hasActiveRun(runs: Run[]): boolean {
  return runs.some((r) => r.status === "queued" || r.status === "running");
}

export function useRunPolling(repoId: string, initialRuns: Run[]): Run[] {
  const [runs, setRuns] = useState<Run[]>(initialRuns);

  useEffect(() => {
    if (!hasActiveRun(runs)) return;

    const interval = setInterval(async () => {
      const updated = await getRuns(repoId);
      setRuns(updated);
      if (!hasActiveRun(updated)) {
        clearInterval(interval);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [repoId, runs]);

  return runs;
}
