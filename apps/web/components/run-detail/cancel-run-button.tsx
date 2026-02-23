"use client";

import { useState } from "react";
import { cancelRun } from "@/lib/api";

interface CancelRunButtonProps {
  runId: string;
  onCancelled: () => void;
}

export function CancelRunButton({ runId, onCancelled }: CancelRunButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  async function handleCancel() {
    setIsLoading(true);
    try {
      const result = await cancelRun(runId);
      if (result.cancelled) {
        onCancelled();
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
      setShowConfirm(false);
    }
  }

  if (showConfirm) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-white/40">Cancel this run?</span>
        <button
          onClick={handleCancel}
          disabled={isLoading}
          className="rounded-full bg-red-500/20 px-3 py-1 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/30 disabled:opacity-50"
        >
          {isLoading ? "Cancelling…" : "Yes, cancel"}
        </button>
        <button
          onClick={() => setShowConfirm(false)}
          className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/40 transition-colors hover:bg-white/5"
        >
          No
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setShowConfirm(true)}
      className="rounded-full border border-red-500/20 bg-red-500/10 px-4 py-1.5 text-xs font-medium text-red-400/80 transition-colors hover:bg-red-500/20 hover:text-red-400"
    >
      Cancel Run
    </button>
  );
}
