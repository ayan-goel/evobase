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
 * Slide-over drawer showing the full detail of a proposal:
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

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${
          isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Proposal details"
        className={`fixed right-0 top-0 z-50 h-full w-full max-w-2xl
          bg-[#0d0d0d] border-l border-white/[0.08] shadow-2xl
          flex flex-col overflow-hidden
          transition-transform duration-300 ease-out
          ${isOpen ? "translate-x-0" : "translate-x-full"}`}
      >
        {proposal && <DrawerContent proposal={proposal} onClose={onClose} />}
      </div>
    </>
  );
}

function DrawerContent({ proposal, onClose }: { proposal: Proposal; onClose: () => void }) {
  const hasVariants = proposal.patch_variants && proposal.patch_variants.length > 1;

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
          <h2 className="text-base font-semibold text-white leading-snug">
            {proposal.summary ?? "Optimization Proposal"}
          </h2>
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
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-7">

        {/* Why this change? */}
        <DrawerSection title="What changed and why">
          <p className="text-sm text-white/60 leading-relaxed">
            {proposal.summary ?? "No description available."}
          </p>
        </DrawerSection>

        {/* Diff */}
        <DrawerSection title="Code change">
          <DiffViewer diff={proposal.diff} />
        </DrawerSection>

        {/* Why this approach won */}
        {proposal.selection_reason && (
          <DrawerSection title="Why this approach was selected">
            <div className="rounded-lg border border-emerald-500/15 bg-emerald-500/[0.05] px-4 py-3">
              <p className="text-sm text-emerald-200/80 leading-relaxed">
                {proposal.selection_reason}
              </p>
            </div>
          </DrawerSection>
        )}

        {/* Other approaches */}
        {hasVariants && (
          <DrawerSection title={`Other approaches tried (${proposal.patch_variants.length})`}>
            <PatchVariants variants={proposal.patch_variants} />
          </DrawerSection>
        )}

      </div>
    </>
  );
}

function DrawerSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-3">
        {title}
      </h3>
      {children}
    </section>
  );
}
