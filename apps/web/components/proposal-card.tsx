"use client";

import { cn } from "@/lib/utils";
import type { Proposal } from "@/lib/types";

interface ProposalCardProps {
  proposal: Proposal;
  onSelect?: () => void;
  className?: string;
}

/** Compact proposal card — click fires onSelect to open the detail drawer. */
export function ProposalCard({ proposal, onSelect, className }: ProposalCardProps) {
  const fileStats = _parseDiffFiles(proposal.diff);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect?.(); }}
      className={cn(
        "group cursor-pointer rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-5",
        "hover:bg-white/[0.05] hover:border-white/[0.10] transition-all select-none",
        className,
      )}
    >
      {/* Title (short) — with summary as fallback for legacy proposals */}
      <p className="text-sm font-medium text-white leading-snug line-clamp-2">
        {proposal.title ?? proposal.summary ?? "Optimization proposal"}
      </p>

      {/* Changed files row */}
      {fileStats.length > 0 && (
        <div className="mt-3 space-y-1">
          {fileStats.slice(0, 3).map((f) => (
            <div key={f.file} className="flex items-center gap-2 min-w-0">
              <span className="shrink-0 text-white/20">
                <FileIcon />
              </span>
              <span className="truncate text-xs text-white/50 font-mono min-w-0 flex-1">
                {f.file}
              </span>
              <span className="shrink-0 flex items-center gap-1 text-xs font-mono tabular-nums">
                {f.added > 0 && (
                  <span className="text-emerald-400">+{f.added}</span>
                )}
                {f.removed > 0 && (
                  <span className="text-red-400">−{f.removed}</span>
                )}
              </span>
            </div>
          ))}
          {fileStats.length > 3 && (
            <p className="text-xs text-white/25 pl-5">
              +{fileStats.length - 3} more file{fileStats.length - 3 !== 1 ? "s" : ""}
            </p>
          )}
        </div>
      )}

      {/* Footer row */}
      <div className="mt-3 flex items-center justify-between">
        <span suppressHydrationWarning className="text-xs text-white/40">
          {_formatRelative(proposal.created_at)}
        </span>

        {proposal.pr_url ? (
          <span className="text-xs text-emerald-400 font-medium">PR created</span>
        ) : (
          <span className="text-xs text-white/30 group-hover:text-white/50 transition-colors">
            View →
          </span>
        )}
      </div>
    </div>
  );
}

function FileIcon() {
  return (
    <svg width="10" height="12" viewBox="0 0 10 12" fill="none" aria-hidden="true">
      <path
        d="M6 1H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4L6 1Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path d="M6 1v3h3" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  );
}

interface FileDiffStats {
  file: string;
  added: number;
  removed: number;
}

/**
 * Parse a unified diff string and return per-file added/removed line counts.
 * Shows the two innermost path segments for readability (e.g. "components/Foo.tsx").
 */
function _parseDiffFiles(diff: string): FileDiffStats[] {
  if (!diff) return [];

  const files: FileDiffStats[] = [];
  let current: FileDiffStats | null = null;

  for (const line of diff.split("\n")) {
    if (line.startsWith("+++ b/") || line.startsWith("+++ ")) {
      const rawPath = line.startsWith("+++ b/")
        ? line.slice(6)
        : line.slice(4);
      const parts = rawPath.trim().split("/");
      const displayPath = parts.length > 2
        ? parts.slice(-2).join("/")
        : rawPath.trim();
      current = { file: displayPath, added: 0, removed: 0 };
      files.push(current);
    } else if (current) {
      if (line.startsWith("+") && !line.startsWith("+++")) {
        current.added++;
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        current.removed++;
      }
    }
  }

  return files;
}

function _formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
