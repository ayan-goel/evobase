"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { createPR } from "@/lib/api";

interface CreatePRButtonProps {
  repoId: string;
  proposalId: string;
  existingPrUrl?: string | null;
  className?: string;
}

/**
 * Triggers PR creation for an accepted proposal.
 * Disabled once a PR exists or while the request is in-flight.
 */
export function CreatePRButton({
  repoId,
  proposalId,
  existingPrUrl,
  className,
}: CreatePRButtonProps) {
  const [prUrl, setPrUrl] = useState<string | null>(existingPrUrl ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (prUrl) {
    return (
      <a
        href={prUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-2 rounded-full bg-emerald-500/10 border border-emerald-500/20",
          "text-emerald-300 text-sm font-medium px-5 h-10 hover:bg-emerald-500/15 transition-colors",
          className,
        )}
      >
        View PR →
      </a>
    );
  }

  async function handleClick() {
    setLoading(true);
    setError(null);
    try {
      const result = await createPR(repoId, proposalId);
      setPrUrl(result.pr_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create PR");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cn("flex flex-col items-start gap-2", className)}>
      <button
        onClick={handleClick}
        disabled={loading}
        className={cn(
          "rounded-full bg-white text-black h-10 px-6 text-sm font-semibold",
          "transition-colors hover:bg-white/90",
          "disabled:opacity-50 disabled:cursor-not-allowed",
        )}
      >
        {loading ? "Creating PR…" : "Create PR"}
      </button>
      {error && (
        <p className="text-xs text-red-300">{error}</p>
      )}
    </div>
  );
}
