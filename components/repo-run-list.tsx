"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { deleteRun, getProposalsByRun, getRuns } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { OnboardingBanner } from "@/components/onboarding-banner";
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const activeRunStatus = getActiveRunStatus(runs);
  const runsRef = useRef(runs);

  useEffect(() => {
    runsRef.current = runs;
  }, [runs]);

  useEffect(() => {
    if (!hasActiveRun(runs)) return;

    const interval = setInterval(async () => {
      if (!hasActiveRun(runsRef.current)) {
        clearInterval(interval);
        return;
      }

      const updated = await fetchRunsWithProposals(repoId);
      setRuns(updated);
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [repoId]);

  function handleQueued(runId: string) {
    setRuns((prev) => [
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const activeRunStatus = useMemo(() => getActiveRunStatus(runs), [runs]);

  useEffect(() => {
    if (!hasActiveRun(runs)) return;
