"use client";

import { useState, useTransition } from "react";
import { deleteRepo } from "@/lib/api";

interface DeleteRepoButtonProps {
  repoId: string;
  repoLabel: string;
}

export function DeleteRepoButton({ repoId, repoLabel }: DeleteRepoButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleDelete() {
    startTransition(async () => {
      try {
        await deleteRepo(repoId);
        window.location.href = "/dashboard";
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove repository.");
        setConfirming(false);
      }
    });
  }

  if (confirming) {
    return (
      <div className="flex shrink-0 items-center gap-2">
        {error && <span className="text-xs text-red-400">{error}</span>}
        <button
          onClick={() => setConfirming(false)}
          disabled={isPending}
          className="rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleDelete}
          disabled={isPending}
          className="rounded-full border border-red-500/40 bg-red-500/20 px-4 py-1.5 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/30 disabled:opacity-50"
        >
          {isPending ? "Removing…" : `Yes, remove ${repoLabel}`}
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="shrink-0 rounded-full border border-red-500/30 bg-red-500/10 px-4 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20"
    >
      Remove repository
    </button>
  );
}
