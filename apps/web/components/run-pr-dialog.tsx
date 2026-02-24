"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
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
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

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

  if (!isOpen || !mounted) return null;

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
                <label
                  key={proposal.id}
                  className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 cursor-pointer hover:bg-white/[0.04] transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(proposal.id)}
                    onChange={() => toggleId(proposal.id)}
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-emerald-400"
                  />
                  <span className="text-sm text-white/75 leading-snug">
                    {proposal.title ?? proposal.summary ?? "Optimization proposal"}
                  </span>
                </label>
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
                className="rounded-lg border border-white/15 px-4 py-1.5 text-xs text-white/50 hover:text-white/70 hover:bg-white/[0.05] transition-colors"
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
      </div>
    </>,
    document.body,
  );
}
