"use client";

import { useMemo } from "react";
import type { RunEvent } from "@/lib/types";

interface FileStatus {
  file: string;
  state: "pending" | "analysing" | "done";
  opportunitiesFound: number;
}

interface FileAnalysisGridProps {
  events: RunEvent[];
}

export function FileAnalysisGrid({ events }: FileAnalysisGridProps) {
  const fileStatuses = useMemo<FileStatus[]>(() => {
    const map = new Map<string, FileStatus>();

    for (const event of events) {
      if (event.type === "discovery.files.selected") {
        const files = (event.data.files as string[]) ?? [];
        for (const file of files) {
          if (!map.has(file)) {
            map.set(file, { file, state: "pending", opportunitiesFound: 0 });
          }
        }
      } else if (event.type === "discovery.file.analysing") {
        const file = event.data.file as string;
        const existing = map.get(file);
        map.set(file, {
          file,
          state: "analysing",
          opportunitiesFound: existing?.opportunitiesFound ?? 0,
        });
      } else if (event.type === "discovery.file.analysed") {
        const file = event.data.file as string;
        const count = (event.data.opportunities_found as number) ?? 0;
        map.set(file, { file, state: "done", opportunitiesFound: count });
      }
    }

    return Array.from(map.values());
  }, [events]);

  if (fileStatuses.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-2">
      {fileStatuses.map(({ file, state, opportunitiesFound }) => (
        <div
          key={file}
          className="group relative flex items-center gap-2.5 rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2.5"
        >
          {/* Full-path tooltip shown on hover */}
          <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-1.5 hidden max-w-[calc(100%+2rem)] rounded-md border border-white/[0.1] bg-[#1a1a1a] px-2.5 py-1.5 group-hover:block">
            <span className="font-mono text-[11px] text-white/80 break-all">{file}</span>
          </div>
          <StatusIcon state={state} />
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-white/75">
            {shortenPath(file)}
          </span>
          {state === "done" && (
            <span
              className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium tabular-nums ${
                opportunitiesFound > 0
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-white/[0.05] text-white/45"
              }`}
            >
              {opportunitiesFound > 0
                ? `${opportunitiesFound} opp${opportunitiesFound !== 1 ? "s" : ""}`
                : "none"}
            </span>
          )}
          {state === "analysing" && (
            <span className="shrink-0 text-[10px] text-white/35 italic">
              analysing…
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function StatusIcon({ state }: { state: FileStatus["state"] }) {
  if (state === "done") {
    return (
      <svg
        className="h-3.5 w-3.5 shrink-0 text-emerald-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2.5}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  if (state === "analysing") {
    return (
      <span className="relative flex h-3.5 w-3.5 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-50" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
      </span>
    );
  }
  return (
    <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-white/[0.14] bg-white/[0.02]" />
  );
}

function shortenPath(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 2) return path;
  return `…/${parts.slice(-2).join("/")}`;
}
