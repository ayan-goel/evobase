"use client";

import React, { useCallback, useEffect, useState, memo } from "react";
import { createPortal } from "react-dom";
import { createRunPR } from "@/lib/api";
import type { Proposal } from "@/lib/types";

interface ProposalRowProps {
  proposal: Proposal;
  isChecked: boolean;
  onToggle: (id: string) => void;
}

const ProposalRow = memo(function ProposalRow({ proposal, isChecked, onToggle }: ProposalRowProps) {
  return (
    <label
      className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 cursor-pointer hover:bg-white/[0.04] transition-colors"
    >
      <input
        type="checkbox"
        checked={isChecked}
        onChange={() => onToggle(proposal.id)}
        className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-emerald-400"
      />
      <span className="text-sm text-white/75 leading-snug">
        {proposal.title ?? proposal.summary ?? "Optimization proposal"}
      </span>
    </label>
  );
});

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
 * Portalled to document.body so the backdrop covers the full viewport
 * regardless of ancestor stacking contexts.
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

  const isBrowser = typeof document !== 'undefined';

  // Pre-select all proposals when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedIds(new Set(proposals.map((p) => p.id)));
      setError(null);
    }
  }, [isOpen, proposals]);

  // Prevent body scroll while open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  const toggleId = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleCreate = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setLoading(true);
    setError(null);

    try {
      const result = await createRunPR(repoId, runId, [...selectedIds]);
      onPRCreated(result.pr_url);
      onClose();
      // Open the PR tab after the dialog is already closing. Some browsers
      // allow window.open() within the same microtask chain as a user gesture;
      // if blocked, fall back to a direct navigation link shown via onPRCreated.
      const tab = window.open(result.pr_url, "_blank", "noopener,noreferrer");
      if (!tab) {
        // Popup was blocked — surface the URL in the parent via onPRCreated so
        // the "View PR" anchor in the run card is immediately clickable.
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PR");
    } finally {
      setLoading(false);
    }
  }, [repoId, runId, selectedIds, onPRCreated, onClose]);

  if (!isOpen || !isBrowser) return null;

  return createPortal(
    <>
      {/* Backdrop — portalled to body so it covers the full screen */}
      <div
        className="fixed inset-0 z-[200] bg-black/75 backdrop-blur-md"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Centering container */}
      <div className="fixed inset-0 z-[210] flex items-center justify-center p-6">
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Create pull request"
          className="w-full max-w-2xl max-h-[85vh] flex flex-col
            bg-[#0d0d0d] border border-white/[0.10] rounded-2xl shadow-2xl
            animate-in fade-in zoom-in-95 duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-white/[0.07] shrink-0">
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

          {/* Body — scrollable */}
          <div className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.12)_transparent] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb:hover]:bg-white/20">
            <p className="text-xs text-white/50 mb-4">
              Select the changes to include in the PR. A single branch will be created with all selected diffs applied.
            </p>

            <div className="space-y-2">
              {proposals.map((proposal) => (
                <ProposalRow
                  key={proposal.id}
                  proposal={proposal}
                  isChecked={selectedIds.has(proposal.id)}
                  onToggle={toggleId}
                />
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-white/[0.07] shrink-0">
            <div className="flex-1 min-w-0">
              {error && <p className="text-xs text-red-300 mb-0.5">{error}</p>}
              <p className="text-xs text-white/30">
                {selectedIds.size} of {proposals.length} change{proposals.length !== 1 ? "s" : ""} selected
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                className="rounded-lg border border-white/15 px-4 py-1.5 text-xs text-white/50 hover:text-white/70 hover:bg-white/[0.05] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={loading || selectedIds.size === 0}
                className="flex items-center gap-2 rounded-lg bg-white px-4 py-1.5 text-xs font-semibold text-black transition-colors hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-3.5 w-3.5 text-black/60 shrink-0" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                    Creating…
                  </>
                ) : (
                  <>
                    <GitHubIcon className="h-3.5 w-3.5 shrink-0" />
                    Create PR on GitHub
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>,
    document.body,
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
