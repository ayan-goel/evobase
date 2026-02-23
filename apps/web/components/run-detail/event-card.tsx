"use client";

import type { ReactElement } from "react";
import { useState } from "react";
import type { RunEvent } from "@/lib/types";

interface EventCardProps {
  event: RunEvent;
}

export function EventCard({ event }: EventCardProps) {
  const renderer = EVENT_RENDERERS[event.type] ?? renderGeneric;
  return renderer(event);
}

// ---------------------------------------------------------------------------
// Per-event-type renderers
// ---------------------------------------------------------------------------

function renderCloneStarted(event: RunEvent) {
  const repo = event.data.repo as string | undefined;
  return (
    <TimelineRow icon="📦" phase="Clone" ts={event.ts}>
      Cloning <Mono>{repo}</Mono>…
    </TimelineRow>
  );
}

function renderCloneCompleted(event: RunEvent) {
  const sha = event.data.sha as string | undefined;
  const msg = event.data.commit_message as string | undefined;
  return (
    <TimelineRow icon="✓" phase="Clone" ts={event.ts} success>
      Clone complete
      {sha ? (
        <span className="ml-2 text-white/30 font-mono text-xs">{sha}</span>
      ) : null}
      {msg ? (
        <span className="ml-1.5 text-white/25 text-xs">— {truncate(msg, 60)}</span>
      ) : null}
    </TimelineRow>
  );
}

function renderDetectionCompleted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const language = d.language as string | undefined;
  const framework = d.framework as string | undefined;
  const packageManager = d.package_manager as string | undefined;
  return (
    <TimelineRow icon="🔍" phase="Detection" ts={event.ts} success>
      <span>
        Detected <Badge>{language}</Badge>
        {framework ? (
          <>
            {" / "}
            <Badge>{framework}</Badge>
          </>
        ) : null}
        {packageManager ? (
          <span className="text-white/30 text-xs ml-2">
            via {packageManager}
          </span>
        ) : null}
      </span>
    </TimelineRow>
  );
}

function renderBaselineAttemptStarted(event: RunEvent) {
  const attempt = event.data.attempt as number | undefined;
  const mode = event.data.mode as string | undefined;
  return (
    <TimelineRow icon="▶" phase="Baseline" ts={event.ts}>
      Starting baseline attempt {attempt}{" "}
      <Badge variant={mode === "adaptive" ? "warn" : "default"}>
        {mode}
      </Badge>
    </TimelineRow>
  );
}

function renderBaselineStepCompleted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const isOk = Boolean(d.success);
  const step = d.step as string | undefined;
  const exitCode = d.exit_code as number | undefined;
  const duration = d.duration as number | undefined;
  const stderrTail = d.stderr_tail as string | undefined;
  const command = d.command as string | undefined;
  return (
    <ExpandableRow
      icon={isOk ? "✓" : "✗"}
      phase="Baseline"
      ts={event.ts}
      success={isOk}
      error={!isOk}
      summary={
        <>
          <Mono>{step}</Mono>{" "}
          {isOk ? (
            <span className="text-emerald-400/70">OK</span>
          ) : (
            <span className="text-red-400/70">FAILED (exit {exitCode})</span>
          )}{" "}
          <span className="text-white/20 text-xs">
            {duration}s
          </span>
        </>
      }
      detail={
        <>
          <p className="text-white/30 text-xs font-mono mb-1">$ {command}</p>
          {stderrTail ? (
            <pre className="text-xs text-red-300/60 whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
              {stderrTail}
            </pre>
          ) : null}
        </>
      }
    />
  );
}

function renderBaselineCompleted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const isOk = Boolean(d.success);
  const failureReason = d.failure_reason as string | undefined;
  const attempts = d.attempts as number | undefined;
  const mode = d.mode as string | undefined;
  return (
    <TimelineRow
      icon={isOk ? "✓" : "✗"}
      phase="Baseline"
      ts={event.ts}
      success={isOk}
      error={!isOk}
    >
      Baseline {isOk ? "passed" : "failed"}
      {!isOk && failureReason ? (
        <span className="text-red-300/60 text-xs ml-2">
          ({failureReason})
        </span>
      ) : null}
      {attempts != null && attempts > 1 ? (
        <span className="text-white/20 text-xs ml-2">
          after {attempts} attempts ({mode})
        </span>
      ) : null}
    </TimelineRow>
  );
}

function renderDiscoveryStarted(event: RunEvent) {
  const llmModel = event.data.llm_model as string | undefined;
  return (
    <TimelineRow icon="🧠" phase="Discovery" ts={event.ts}>
      Agent analyzing codebase
      {llmModel ? (
        <span className="text-white/20 text-xs ml-2">
          using {llmModel}
        </span>
      ) : null}
    </TimelineRow>
  );
}

function renderFilesSelected(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const count = (d.count as number | undefined) ?? 0;
  const files = Array.isArray(d.files) ? (d.files as string[]) : [];
  return (
    <ExpandableRow
      icon="📂"
      phase="Discovery"
      ts={event.ts}
      summary={
        <>
          Selected{" "}
          <Badge>{count} file{count !== 1 ? "s" : ""}</Badge>{" "}
          <span className="text-white/30 text-xs">for analysis</span>
        </>
      }
      detail={
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          {files.map((f) => (
            <Mono key={f}>{shortenPath(f)}</Mono>
          ))}
        </div>
      }
    />
  );
}

function renderFileAnalysing(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const file = d.file as string | undefined;
  const fileIndex = (d.file_index as number | undefined) ?? 0;
  const totalFiles = (d.total_files as number | undefined) ?? 0;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/[0.04] bg-transparent px-4 py-2 text-sm opacity-60">
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/50" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
      </span>
      <span className="min-w-0 flex-1 text-white/40 text-xs">
        Analysing <Mono>{file ? shortenPath(file) : "…"}</Mono>
      </span>
      <span className="shrink-0 text-[10px] text-white/20 font-mono tabular-nums">
        {fileIndex + 1}/{totalFiles}
      </span>
    </div>
  );
}

function renderFileAnalysed(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const file = d.file as string | undefined;
  const count = (d.opportunities_found as number | undefined) ?? 0;
  const fileIndex = (d.file_index as number | undefined) ?? 0;
  const totalFiles = (d.total_files as number | undefined) ?? 0;
  const hasOpps = count > 0;
  return (
    <TimelineRow icon="✓" phase="Discovery" ts={event.ts} success={hasOpps}>
      <Mono>{file ? shortenPath(file) : "…"}</Mono>
      <span className="text-white/30 text-xs">—</span>
      {hasOpps ? (
        <span className="text-emerald-400/70 text-xs">
          {count} opportunit{count !== 1 ? "ies" : "y"} found
        </span>
      ) : (
        <span className="text-white/25 text-xs">nothing to improve</span>
      )}
      <span className="text-white/15 text-[10px] ml-auto tabular-nums font-mono">
        {fileIndex + 1}/{totalFiles}
      </span>
    </TimelineRow>
  );
}

function renderPatchApproachStarted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const location = d.location as string | undefined;
  const approachIndex = (d.approach_index as number | undefined) ?? 0;
  const totalApproaches = (d.total_approaches as number | undefined) ?? 1;
  const approachDesc = d.approach_desc as string | undefined;
  const oppType = d.type as string | undefined;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/[0.04] bg-transparent px-4 py-2.5 text-sm opacity-70">
      <span className="shrink-0 text-base">⚙</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap text-xs text-white/40">
          Generating approach{" "}
          <span className="font-mono text-white/60">
            {approachIndex + 1}/{totalApproaches}
          </span>
          {oppType ? <Badge variant="default">{oppType}</Badge> : null}
          <Mono>{location ? shortenPath(location) : "…"}</Mono>
        </div>
        {approachDesc ? (
          <p className="mt-0.5 text-[11px] text-white/25 truncate">
            {approachDesc}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function renderPatchApproachCompleted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const success = Boolean(d.success);
  const linesChanged = d.lines_changed as number | null | undefined;
  const touchedFiles = Array.isArray(d.touched_files)
    ? (d.touched_files as string[])
    : [];
  const approachIndex = (d.approach_index as number | undefined) ?? 0;
  return (
    <TimelineRow
      icon={success ? "⊕" : "⊗"}
      phase="Patching"
      ts={event.ts}
      success={success}
      error={!success}
    >
      {success ? (
        <>
          <span className="text-emerald-400/70">Patch ready</span>
          {linesChanged != null ? (
            <span className="text-white/30 text-xs">+{linesChanged} lines</span>
          ) : null}
          {touchedFiles.length > 0 ? (
            <span className="text-white/20 text-xs">
              {touchedFiles.length} file{touchedFiles.length !== 1 ? "s" : ""}
            </span>
          ) : null}
        </>
      ) : (
        <span className="text-red-400/70">
          Approach {approachIndex + 1} failed
        </span>
      )}
    </TimelineRow>
  );
}

function renderValidationCandidateStarted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const candidateIndex = (d.candidate_index as number | undefined) ?? 0;
  const location = d.location as string | undefined;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-white/[0.04] bg-transparent px-4 py-2 text-sm opacity-60">
      <span className="shrink-0 text-sm">🧪</span>
      <span className="text-white/40 text-xs">
        Validating candidate{" "}
        <span className="font-mono text-white/60">{candidateIndex + 1}</span>
        {location ? (
          <>
            {" "}—{" "}
            <Mono>{shortenPath(location)}</Mono>
          </>
        ) : null}
      </span>
    </div>
  );
}

function renderOpportunityFound(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const type = d.type as string | undefined;
  const location = d.location as string | undefined;
  const rationale = d.rationale as string | undefined;
  const approaches = Array.isArray(d.approaches) ? (d.approaches as string[]) : [];
  return (
    <ExpandableRow
      icon="💡"
      phase="Discovery"
      ts={event.ts}
      summary={
        <>
          Found opportunity: <Badge>{type}</Badge>{" "}
          <Mono>{location}</Mono>
        </>
      }
      detail={
        <>
          <p className="text-white/40 text-xs mb-2">{rationale}</p>
          {approaches.length > 0 ? (
            <div className="text-xs text-white/30">
              <p className="font-medium text-white/40 mb-1">
                Approaches ({approaches.length}):
              </p>
              <ol className="list-decimal list-inside space-y-0.5">
                {approaches.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
            </div>
          ) : null}
        </>
      }
    />
  );
}

function renderDiscoveryCompleted(event: RunEvent) {
  const count = (event.data.count as number | undefined) ?? 0;
  return (
    <TimelineRow icon="✓" phase="Discovery" ts={event.ts} success>
      Discovery complete — {count} opportunit{count === 1 ? "y" : "ies"} found
    </TimelineRow>
  );
}

function renderValidationVerdict(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const isOk = Boolean(d.accepted);
  const opportunity = d.opportunity as string | undefined;
  const confidence = d.confidence as string | undefined;
  const reason = d.reason as string | undefined;
  const gatesPassed = Array.isArray(d.gates_passed) ? (d.gates_passed as string[]) : [];
  const gatesFailed = Array.isArray(d.gates_failed) ? (d.gates_failed as string[]) : [];
  const approachesTried = (d.approaches_tried as number | undefined) ?? 0;
  return (
    <ExpandableRow
      icon={isOk ? "✓" : "✗"}
      phase="Validation"
      ts={event.ts}
      success={isOk}
      error={!isOk}
      summary={
        <>
          <Mono>{opportunity}</Mono>{" "}
          {isOk ? (
            <span className="text-emerald-400/70">accepted</span>
          ) : (
            <span className="text-red-400/70">rejected</span>
          )}
          {confidence ? (
            <Badge variant={confidence === "high" ? "success" : confidence === "medium" ? "warn" : "default"}>
              {confidence}
            </Badge>
          ) : null}
          {approachesTried > 1 ? (
            <span className="text-white/20 text-xs ml-1">
              ({approachesTried} approaches)
            </span>
          ) : null}
        </>
      }
      detail={
        <>
          {reason ? <p className="text-white/40 text-xs mb-2">{reason}</p> : null}
          {gatesPassed.length > 0 ? (
            <p className="text-emerald-400/50 text-xs">
              Passed: {gatesPassed.join(", ")}
            </p>
          ) : null}
          {gatesFailed.length > 0 ? (
            <p className="text-red-400/50 text-xs">
              Failed: {gatesFailed.join(", ")}
            </p>
          ) : null}
        </>
      }
    />
  );
}

function renderSelectionCompleted(event: RunEvent) {
  const reason = event.data.reason as string | undefined;
  return (
    <TimelineRow icon="🏆" phase="Selection" ts={event.ts} success>
      Best approach selected
      {reason ? (
        <span className="text-white/30 text-xs ml-2">
          — {reason}
        </span>
      ) : null}
    </TimelineRow>
  );
}

function renderRunCompleted(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const proposalsCreated = (d.proposals_created as number | undefined) ?? 0;
  const candidatesAttempted = (d.candidates_attempted as number | undefined) ?? 0;
  const accepted = (d.accepted as number | undefined) ?? 0;
  return (
    <TimelineRow icon="🎉" phase="Done" ts={event.ts} success>
      Run complete — {proposalsCreated} proposal{proposalsCreated !== 1 ? "s" : ""} created
      <span className="text-white/20 text-xs ml-2">
        ({accepted}/{candidatesAttempted} candidates accepted)
      </span>
    </TimelineRow>
  );
}

function renderRunFailed(event: RunEvent) {
  const d = event.data as Record<string, unknown>;
  const failureStep = d.failure_step as string | undefined;
  const detail = (d.failure_reason_code ?? d.reason ?? d.error) as string | undefined;
  return (
    <TimelineRow icon="✗" phase="Error" ts={event.ts} error>
      Run failed
      {failureStep ? (
        <span className="text-red-300/60 text-xs ml-2">
          at {failureStep}
        </span>
      ) : null}
      {detail ? (
        <span className="text-red-300/50 text-xs ml-1">
          — {detail}
        </span>
      ) : null}
    </TimelineRow>
  );
}

function renderRunCancelled(event: RunEvent) {
  return (
    <TimelineRow icon="⏹" phase="Cancelled" ts={event.ts} error>
      Run cancelled by user
    </TimelineRow>
  );
}

function renderGeneric(event: RunEvent) {
  return (
    <TimelineRow icon="·" phase={event.phase} ts={event.ts}>
      {event.type}
    </TimelineRow>
  );
}

const EVENT_RENDERERS: Record<string, (e: RunEvent) => ReactElement> = {
  "clone.started": renderCloneStarted,
  "clone.completed": renderCloneCompleted,
  "detection.completed": renderDetectionCompleted,
  "baseline.attempt.started": renderBaselineAttemptStarted,
  "baseline.step.completed": renderBaselineStepCompleted,
  "baseline.completed": renderBaselineCompleted,
  "discovery.started": renderDiscoveryStarted,
  "discovery.files.selected": renderFilesSelected,
  "discovery.file.analysing": renderFileAnalysing,
  "discovery.file.analysed": renderFileAnalysed,
  "discovery.opportunity.found": renderOpportunityFound,
  "discovery.completed": renderDiscoveryCompleted,
  "patch.approach.started": renderPatchApproachStarted,
  "patch.approach.completed": renderPatchApproachCompleted,
  "validation.candidate.started": renderValidationCandidateStarted,
  "validation.verdict": renderValidationVerdict,
  "selection.completed": renderSelectionCompleted,
  "run.completed": renderRunCompleted,
  "run.failed": renderRunFailed,
  "run.cancelled": renderRunCancelled,
};

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

function TimelineRow({
  icon,
  phase,
  ts,
  success,
  error,
  children,
}: {
  icon: string;
  phase: string;
  ts: string;
  success?: boolean;
  error?: boolean;
  children: React.ReactNode;
}) {
  const time = ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  return (
    <div
      className={`
        flex items-start gap-3 rounded-lg border px-4 py-3 text-sm
        ${error
          ? "border-red-500/20 bg-red-500/[0.04]"
          : success
            ? "border-emerald-500/15 bg-emerald-500/[0.03]"
            : "border-white/[0.06] bg-white/[0.02]"
        }
      `}
    >
      <span className="shrink-0 w-5 text-center">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          {children}
        </div>
      </div>
      <span className="shrink-0 text-[10px] text-white/20 font-mono tabular-nums">
        {time}
      </span>
    </div>
  );
}

function ExpandableRow({
  icon,
  phase,
  ts,
  success,
  error,
  summary,
  detail,
}: {
  icon: string;
  phase: string;
  ts: string;
  success?: boolean;
  error?: boolean;
  summary: React.ReactNode;
  detail: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const time = ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";

  return (
    <div
      className={`
        rounded-lg border text-sm
        ${error
          ? "border-red-500/20 bg-red-500/[0.04]"
          : success
            ? "border-emerald-500/15 bg-emerald-500/[0.03]"
            : "border-white/[0.06] bg-white/[0.02]"
        }
      `}
    >
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg"
      >
        <span className="shrink-0 w-5 text-center">{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">{summary}</div>
        </div>
        <span className="shrink-0 text-[10px] text-white/20 font-mono tabular-nums">
          {time}
        </span>
        <span className="shrink-0 text-white/20 text-xs ml-1">
          {isOpen ? "▾" : "▸"}
        </span>
      </button>
      {isOpen && (
        <div className="px-4 pb-3 pl-12 border-t border-white/[0.04] pt-2">
          {detail}
        </div>
      )}
    </div>
  );
}

function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "warn";
}) {
  const colors = {
    default: "bg-white/10 text-white/60",
    success: "bg-emerald-500/15 text-emerald-400/80",
    warn: "bg-amber-500/15 text-amber-400/80",
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-medium ${colors[variant]}`}
    >
      {children}
    </span>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <code className="text-xs font-mono text-white/50">{children}</code>;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

function shortenPath(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 2) return path;
  return `…/${parts.slice(-2).join("/")}`;
}
