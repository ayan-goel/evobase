"use client";

import { useEffect, useState } from "react";
import { createRunPR } from "@/lib/api";
import type { Proposal } from "@/lib/types";

interface RunPRDialogProps {
  isOpen: boolean;
  onClose: () => void;
  repoId: string;
  runId: string;
  proposals: Proposal[];
  onPRCreated: (prUrl: string) => void;
}

/**
 * Modal dialog for creating a run-level GitHub PR.
 * Shows a checkbox list of all proposals — user selects which to include.
 */
export function RunPRDialog({
  isOpen,
  onClose,
  repoId,
  runId,
  proposals,
  onPRCreated,
}: RunPRDialogProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-select all proposals when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedIds(new Set(proposals.map((p) => p.id)));
      setError(null);
    }
  }, [isOpen, proposals]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  function toggleId(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCreate() {
    if (selectedIds.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await createRunPR(repoId, runId, [...selectedIds]);
      onPRCreated(result.pr_url);
      window.open(result.pr_url, "_blank", "noopener,noreferrer");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PR");
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-md"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Create pull request"
        className="fixed left-1/2 top-1/2 z-[110] w-full max-w-md -translate-x-1/2 -translate-y-1/2
          bg-[#0d0d0d] border border-white/[0.10] rounded-xl shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.07]">
          <h2 className="text-sm font-semibold text-white">Open PR on GitHub</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-colors"
            aria-label="Close"
          >
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M2 2l12 12M14 2L2 14" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className="text-xs text-white/50 mb-4">
            Select the changes to include in the PR. A single branch will be created with all selected diffs applied.
          </p>

          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {proposals.map((proposal) => (
              <label
                key={proposal.id}
                className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 cursor-pointer hover:bg-white/[0.04] transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(proposal.id)}
                  onChange={() => toggleId(proposal.id)}
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-emerald-400"
                />
                <span className="text-xs text-white/70 leading-snug">
                  {proposal.summary ?? "Optimization proposal"}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-white/[0.07]">
          <div className="flex-1">
            {error && <p className="text-xs text-red-300">{error}</p>}
            <p className="text-xs text-white/30">
              {selectedIds.size} of {proposals.length} change{proposals.length !== 1 ? "s" : ""} selected
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white/50 hover:text-white/70 hover:bg-white/[0.05] transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={loading || selectedIds.size === 0}
              className="rounded-lg bg-white px-4 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? "Creating…" : "Create PR on GitHub"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
