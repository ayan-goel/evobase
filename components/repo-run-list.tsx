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
  const { events, currentPhase, isDone } = useRunEvents(runId, true);
  const status = useMemo(() => deriveStatus(events), [events]);

  const visibleStats = useMemo(() => {
    const stats: { label: string; value: number | string; show: boolean }[] = [
      {
        label: "Opportunities",
        value: status.opportunitiesFound,
        show: status.opportunitiesFound > 0,
      },
      {
        label: "Approaches",
        value: status.approachesTested,
        show: status.approachesTested > 0,
      },
      {
        label: "Validated",
        value: status.candidatesValidated,
        show: status.candidatesValidated > 0,
      },
      {
        label: "Accepted",
        value: status.candidatesAccepted,
        show: status.candidatesValidated > 0,
      },
    ];
    return stats.filter((s) => s.show);
  }, [
    status.opportunitiesFound,
    status.approachesTested,
    status.candidatesValidated,
    status.candidatesAccepted,
  ]);

  return (
    <div className="space-y-4">
