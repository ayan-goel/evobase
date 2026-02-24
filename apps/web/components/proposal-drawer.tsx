"use client";

import { useEffect } from "react";
import { DiffViewer } from "@/components/diff-viewer";
import { PatchVariants } from "@/components/patch-variants";
import { ConfidenceBadge } from "@/components/confidence-badge";
import type { Proposal } from "@/lib/types";

interface ProposalDrawerProps {
  proposal: Proposal | null;
  onClose: () => void;
}

/**
 * Centered modal dialog showing the full detail of a proposal:
 * diff, why it was changed, other approaches tried, and why this one won.
 */
export function ProposalDrawer({ proposal, onClose }: ProposalDrawerProps) {
  const isOpen = proposal !== null;

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  // Prevent body scroll while open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop — above the navbar (z-50) so the entire screen is blurred */}
      <div
        className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-md"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Centering container */}
      <div className="fixed inset-0 z-[110] flex items-center justify-center p-6">
        {/* Panel */}
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Proposal details"
          className="relative w-full max-w-2xl max-h-[90vh] rounded-2xl
            bg-[#0d0d0d] border border-white/[0.08] shadow-2xl
            flex flex-col overflow-hidden
            animate-in fade-in zoom-in-95 duration-200"
        >
          {proposal && <ModalContent proposal={proposal} onClose={onClose} />}
        </div>
      </div>
    </>
  );
}

function ModalContent({ proposal, onClose }: { proposal: Proposal; onClose: () => void }) {
  const hasVariants = proposal.patch_variants && proposal.patch_variants.length > 1;

  // Prefer the selected variant's LLM verdict reason over the internal
  // confidence label stored in selection_reason.
  const selectedVariant = proposal.patch_variants?.find(v => v.is_selected);
  const verdictReason =
    selectedVariant?.validation_result?.reason ||
    _filterSelectionReason(proposal.selection_reason);

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-white/[0.07] shrink-0">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <ConfidenceBadge confidence={proposal.confidence} />
            {proposal.approaches_tried !== null && proposal.approaches_tried > 1 && (
              <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-0.5 text-xs text-white/40">
                Best of {proposal.approaches_tried} approaches
              </span>
            )}
          </div>
          {(proposal.title || proposal.summary) && (
            <h2 className="text-base font-semibold text-white leading-snug">
              {proposal.title ?? _shortTitle(proposal.summary)}
            </h2>
          )}
        </div>
        <button
          onClick={onClose}
          className="shrink-0 mt-0.5 rounded-md p-1.5 text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-colors"
          aria-label="Close"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M2 2l12 12M14 2L2 14" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-7 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.12)_transparent] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb:hover]:bg-white/20">

        {/* What changed and why */}
        <ModalSection title="What changed and why">
          <p className="text-sm text-white/60 leading-relaxed">
            {proposal.summary ?? "No description available."}
          </p>
        </ModalSection>

        {/* Diff */}
        <ModalSection title="Code change">
          <DiffViewer diff={proposal.diff} />
        </ModalSection>

        {/* Why this approach won */}
        {verdictReason && (
          <ModalSection title="Why this approach was selected">
            <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/[0.05] px-4 py-3">
              <p className="text-sm text-emerald-200/80 leading-relaxed">
                {verdictReason}
              </p>
            </div>
          </ModalSection>
        )}

        {/* Other approaches */}
        {hasVariants && (
          <ModalSection title={`Other approaches tried (${proposal.patch_variants.length})`}>
            <PatchVariants variants={proposal.patch_variants} />
          </ModalSection>
        )}

      </div>
    </>
  );
}

function ModalSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-3">
        {title}
      </h3>
      {children}
    </section>
  );
}

/** Truncate a long summary to a brief fallback title for legacy proposals. */
function _shortTitle(s: string | null): string {
  if (!s) return "Optimization Proposal";
  return s.length <= 72 ? s : s.slice(0, 69) + "…";
}

/**
 * Filter out bare confidence labels from selection_reason.
 * Returns null when the string is just an internal confidence label
 * with no meaningful user-facing content.
 */
function _filterSelectionReason(reason: string | null | undefined): string | null {
  if (!reason) return null;
  // Strip if it's purely a confidence label (optionally with rejection counts)
  const bare = /^(high|medium|low) confidence(;\s*\d+ other approach(es)? rejected)?$/i;
  return bare.test(reason.trim()) ? null : reason;
}
