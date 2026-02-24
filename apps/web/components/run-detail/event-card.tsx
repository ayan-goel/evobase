"use client";

import type { ReactElement } from "react";
import { useState } from "react";
import { DiffViewer } from "@/components/diff-viewer";
import { PatchReasoningPanel } from "@/components/patch-reasoning-panel";
import {
  ValidationAttemptsPanel,
  type ValidationAttemptSummary,
  type ValidationBenchmarkSummary,
} from "@/components/run-detail/validation-attempts-panel";
import type { RunEvent, ThinkingTrace } from "@/lib/types";

interface EventCardProps {
  event: RunEvent;
}

interface DiscoveryFileOpportunity {
  file: string;
  location: string;
  type: string;
  rationale: string;
  riskLevel: string;
  affectedLines: number;
  approaches: string[];
}

interface PatchApproachStartedDetail {
  approachDescFull: string | null;
  rationale: string | null;
  riskLevel: string | null;
  affectedLines: number | null;
}

interface PatchApproachCompletedDetail {
  location: string | null;
  type: string | null;
  totalApproaches: number | null;
  approachDescFull: string | null;
  explanation: string | null;
  diff: string | null;
  patchTrace: ThinkingTrace | null;
  failureStage: string | null;
  failureReason: string | null;
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
    <div className="flex items-center gap-3 rounded-lg border border-blue-500/25 bg-blue-500/[0.04] px-4 py-3 text-sm">
      <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/40" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
      </span>
      <div className="flex min-w-0 flex-1 items-center gap-2 flex-wrap">
        <Mono>{file ? shortenPath(file) : "…"}</Mono>
        <span className="text-xs italic text-blue-400/60">analysing…</span>
      </div>
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
  const opportunities = parseDiscoveryFileOpportunities(d.opportunities);
  const summary = (
    <>
      <span title={file}>
        <Mono>{file ? shortenPath(file) : "…"}</Mono>
      </span>
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
    </>
  );

  if (hasOpps && opportunities.length > 0) {
    return (
      <ExpandableRow
        icon="✓"
        phase="Discovery"
        ts={event.ts}
        success
        summary={summary}
        detail={
          <div className="space-y-2">
            {opportunities.map((opp, idx) => (
              <div
                key={`${opp.location}-${idx}`}
                className="rounded-md border border-white/[0.05] bg-white/[0.02] px-3 py-2"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge>{opp.type}</Badge>
                  <Badge variant={riskBadgeVariant(opp.riskLevel)}>
                    risk: {opp.riskLevel}
                  </Badge>
                  <span title={opp.location || opp.file}>
                    <Mono>{opp.location || opp.file}</Mono>
                  </span>
                  {opp.affectedLines > 0 ? (
                    <span className="text-white/20 text-xs">
                      {opp.affectedLines} line{opp.affectedLines !== 1 ? "s" : ""}
                    </span>
                  ) : null}
                </div>
                {opp.rationale ? (
                  <p className="mt-1.5 text-xs text-white/40 leading-relaxed">
                    <RichText text={opp.rationale} />
                  </p>
                ) : null}
                {opp.approaches.length > 0 ? (
                  <div className="mt-2 text-xs text-white/30">
                    <p className="font-medium text-white/40 mb-1">
                      Approaches ({opp.approaches.length}):
                    </p>
                    <ol className="list-decimal list-inside space-y-1">
                      {opp.approaches.map((approach, approachIdx) => (
                        <li key={approachIdx} className="leading-relaxed">
                          <RichText text={approach} />
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        }
      />
    );
  }

  return (
    <TimelineRow icon="✓" phase="Discovery" ts={event.ts} success={hasOpps}>
      {summary}
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
  const detail = parsePatchApproachStartedDetail(d);
  const summary = (
    <>
      <span className="text-white/40 text-xs">Generating approach</span>
      <span className="font-mono text-white/60 text-xs">
        {approachIndex + 1}/{totalApproaches}
      </span>
      {oppType ? <Badge variant="default">{oppType}</Badge> : null}
      <span title={location}>
        <Mono>{location ? shortenPath(location) : "…"}</Mono>
      </span>
      {approachDesc ? (
        <span className="text-[11px] text-white/25 truncate max-w-[28rem]">
          {approachDesc}
        </span>
      ) : null}
    </>
  );

  if (detail) {
    return (
      <ExpandableRow
        icon="⚙"
        phase="Patching"
        ts={event.ts}
        summary={summary}
        detail={
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              {oppType ? <Badge>{oppType}</Badge> : null}
              {detail.riskLevel ? (
                <Badge variant={riskBadgeVariant(detail.riskLevel)}>
                  risk: {detail.riskLevel}
                </Badge>
              ) : null}
              {detail.affectedLines != null && detail.affectedLines > 0 ? (
                <span className="text-xs text-white/30">
                  {detail.affectedLines} affected line{detail.affectedLines !== 1 ? "s" : ""}
                </span>
              ) : null}
            </div>
            {location ? (
              <p className="text-xs text-white/35">
                Location:{" "}
                <span title={location}>
                  <Mono>{location}</Mono>
                </span>
              </p>
            ) : null}
            {detail.rationale ? (
              <p className="text-xs text-white/40 leading-relaxed">
                <RichText text={detail.rationale} />
              </p>
            ) : null}
            {detail.approachDescFull ? (
              <div>
                <p className="text-xs font-medium text-white/40 mb-1">
                  Full approach
                </p>
                <p className="text-xs text-white/60 leading-relaxed">
                  <RichText text={detail.approachDescFull} />
                </p>
              </div>
            ) : null}
          </div>
        }
      />
    );
  }

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
  const detail = parsePatchApproachCompletedDetail(d);
  const summary = success ? (
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
  );

  if (detail) {
    return (
      <ExpandableRow
        icon={success ? "⊕" : "⊗"}
        phase="Patching"
        ts={event.ts}
        success={success}
        error={!success}
        summary={summary}
        detail={
          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              {detail.type ? <Badge>{detail.type}</Badge> : null}
              {detail.location ? (
                <span title={detail.location}>
                  <Mono>{detail.location}</Mono>
                </span>
              ) : null}
              {detail.totalApproaches != null ? (
                <span className="text-xs text-white/25">
                  {detail.totalApproaches} approach{detail.totalApproaches !== 1 ? "es" : ""} total
                </span>
              ) : null}
            </div>

            {detail.approachDescFull ? (
              <p className="text-xs text-white/50 leading-relaxed">
                <RichText text={detail.approachDescFull} />
              </p>
            ) : null}

            {!success && (detail.failureStage || detail.failureReason) ? (
              <div className="rounded-md border border-red-500/15 bg-red-500/[0.04] px-3 py-2">
                {detail.failureStage ? (
                  <p className="text-xs text-red-300/80">
                    Failure stage: {detail.failureStage}
                  </p>
                ) : null}
                {detail.failureReason ? (
                  <p className="text-xs text-red-300/65 mt-0.5">
                    {detail.failureReason}
                  </p>
                ) : null}
              </div>
            ) : null}

            {detail.explanation ? (
              <div>
                <p className="text-xs font-medium text-white/40 mb-1">
                  Patch explanation
                </p>
                <p className="text-xs text-white/55 leading-relaxed">
                  <RichText text={detail.explanation} />
                </p>
              </div>
            ) : null}

            {touchedFiles.length > 0 ? (
              <div>
                <p className="text-xs font-medium text-white/40 mb-1">
                  Touched files
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {touchedFiles.map((f) => (
                    <span key={f} title={f}>
                      <Mono>{shortenPath(f)}</Mono>
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {detail.diff ? (
              <div>
                <p className="text-xs font-medium text-white/40 mb-1.5">Code change</p>
                <DiffViewer diff={detail.diff} />
              </div>
            ) : null}

            {detail.patchTrace ? (
              <MiniCollapsible label="Patch generation reasoning">
                <PatchReasoningPanel trace={detail.patchTrace} />
              </MiniCollapsible>
            ) : null}
          </div>
        }
      />
    );
  }

  return (
    <TimelineRow
      icon={success ? "⊕" : "⊗"}
      phase="Patching"
      ts={event.ts}
      success={success}
      error={!success}
    >
      {summary}
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
  const attempts = parseValidationAttempts(d.attempts);
  const benchmarkComparison = parseValidationBenchmarkComparison(d.benchmark_comparison);
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
          {benchmarkComparison ? (
            <div className="mt-2 rounded-md border border-white/[0.05] bg-white/[0.02] px-3 py-2 text-xs">
              <p className="text-white/40 font-medium mb-1">Benchmark comparison</p>
              <p className="text-white/55">
                {benchmarkComparison.improvement_pct >= 0 ? "+" : ""}
                {benchmarkComparison.improvement_pct.toFixed(1)}% vs baseline
                {" · "}
                baseline {benchmarkComparison.baseline_duration_seconds.toFixed(3)}s
                {" · "}
                candidate {benchmarkComparison.candidate_duration_seconds.toFixed(3)}s
              </p>
            </div>
          ) : null}
          {attempts.length > 0 ? (
            <div className="mt-2">
              <p className="text-xs font-medium text-white/40 mb-2">
                Validation attempts ({attempts.length})
              </p>
              <ValidationAttemptsPanel attempts={attempts} />
            </div>
          ) : null}
        </>
      }
    />
  );
}

function renderSelectionCompleted(event: RunEvent) {
  const patchTitle = event.data.patch_title as string | undefined;
  // Prefer the LLM verdict reason (added in newer runs); fall back to
  // filtering out bare internal confidence labels from the legacy field.
  const verdictReason = event.data.verdict_reason as string | undefined;
  const legacyReason = event.data.reason as string | undefined;
  const displayReason = verdictReason ?? _filterBareConfidenceLabel(legacyReason);
  return (
    <TimelineRow icon="🏆" phase="Selection" ts={event.ts} success>
      <div className="flex flex-col gap-0.5 min-w-0">
        <span>
          Best approach selected
          {patchTitle ? (
            <span className="text-white/50 ml-2">— {patchTitle}</span>
          ) : null}
        </span>
        {displayReason ? (
          <span className="text-white/30 text-xs leading-relaxed">{displayReason}</span>
        ) : null}
      </div>
    </TimelineRow>
  );
}

/** Returns null when the string is just an internal confidence label. */
function _filterBareConfidenceLabel(s: string | undefined): string | null {
  if (!s) return null;
  const bare = /^(high|medium|low) confidence(;\s*\d+ other approach(es)? rejected)?$/i;
  return bare.test(s.trim()) ? null : s;
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

function MiniCollapsible({
  label,
  children,
  defaultOpen = false,
}: {
  label: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-md border border-white/[0.05]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-white/45 hover:text-white/65"
        aria-expanded={open}
      >
        <span>{label}</span>
        <span className="text-white/25">{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <div className="border-t border-white/[0.04] p-3">
          {children}
        </div>
      ) : null}
    </div>
  );
}


function parseDiscoveryFileOpportunities(value: unknown): DiscoveryFileOpportunity[] {
  if (!Array.isArray(value)) return [];

  const result: DiscoveryFileOpportunity[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const d = item as Record<string, unknown>;
    const approaches = Array.isArray(d.approaches)
      ? d.approaches.filter((a): a is string => typeof a === "string" && a.length > 0)
      : [];
    const affectedLinesRaw = d.affected_lines;
    const affectedLines =
      typeof affectedLinesRaw === "number" && Number.isFinite(affectedLinesRaw)
        ? affectedLinesRaw
        : 0;
    result.push({
      file: typeof d.file === "string" ? d.file : "",
      location: typeof d.location === "string" ? d.location : "",
      type: typeof d.type === "string" && d.type ? d.type : "opportunity",
      rationale: typeof d.rationale === "string" ? d.rationale : "",
      riskLevel:
        typeof d.risk_level === "string" && d.risk_level
          ? d.risk_level
          : "unknown",
      affectedLines,
      approaches,
    });
  }

  return result;
}

function riskBadgeVariant(riskLevel: string): "default" | "success" | "warn" {
  if (riskLevel === "low") return "success";
  if (riskLevel === "medium") return "warn";
  return "default";
}

function parsePatchApproachStartedDetail(
  data: Record<string, unknown>,
): PatchApproachStartedDetail | null {
  const hasEnriched =
    "approach_desc_full" in data ||
    "rationale" in data ||
    "risk_level" in data ||
    "affected_lines" in data;
  if (!hasEnriched) return null;

  const affectedLinesRaw = data.affected_lines;
  const affectedLines =
    typeof affectedLinesRaw === "number" && Number.isFinite(affectedLinesRaw)
      ? affectedLinesRaw
      : null;

  return {
    approachDescFull:
      typeof data.approach_desc_full === "string" ? data.approach_desc_full : null,
    rationale: typeof data.rationale === "string" ? data.rationale : null,
    riskLevel: typeof data.risk_level === "string" ? data.risk_level : null,
    affectedLines,
  };
}

function parsePatchApproachCompletedDetail(
  data: Record<string, unknown>,
): PatchApproachCompletedDetail | null {
  const hasEnriched =
    "approach_desc_full" in data ||
    "patchgen_tries" in data ||
    "patch_trace" in data ||
    "diff" in data ||
    "failure_stage" in data ||
    "failure_reason" in data;
  if (!hasEnriched) return null;

  const totalApproachesRaw = data.total_approaches;
  const totalApproaches =
    typeof totalApproachesRaw === "number" && Number.isFinite(totalApproachesRaw)
      ? totalApproachesRaw
      : null;

  return {
    location: typeof data.location === "string" ? data.location : null,
    type: typeof data.type === "string" ? data.type : null,
    totalApproaches,
    approachDescFull:
      typeof data.approach_desc_full === "string" ? data.approach_desc_full : null,
    explanation: typeof data.explanation === "string" ? data.explanation : null,
    diff: typeof data.diff === "string" ? data.diff : null,
    patchTrace: parseThinkingTrace(data.patch_trace),
    failureStage:
      typeof data.failure_stage === "string" ? data.failure_stage : null,
    failureReason:
      typeof data.failure_reason === "string" ? data.failure_reason : null,
  };
}

function parseValidationAttempts(value: unknown): ValidationAttemptSummary[] {
  if (!Array.isArray(value)) return [];
  const result: ValidationAttemptSummary[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const d = item as Record<string, unknown>;
    const steps = Array.isArray(d.steps) ? d.steps : [];
    const parsedSteps = steps
      .filter((s): s is Record<string, unknown> => Boolean(s) && typeof s === "object")
      .map((step) => ({
        name: typeof step.name === "string" ? step.name : "",
        command: typeof step.command === "string" ? step.command : "",
        exit_code:
          typeof step.exit_code === "number" && Number.isFinite(step.exit_code)
            ? step.exit_code
            : 0,
        duration_seconds:
          typeof step.duration_seconds === "number" && Number.isFinite(step.duration_seconds)
            ? step.duration_seconds
            : 0,
        stdout_lines:
          typeof step.stdout_lines === "number" && Number.isFinite(step.stdout_lines)
            ? step.stdout_lines
            : 0,
        stderr_lines:
          typeof step.stderr_lines === "number" && Number.isFinite(step.stderr_lines)
            ? step.stderr_lines
            : 0,
        is_success: Boolean(step.is_success),
      }));
    result.push({
      attempt_number:
        typeof d.attempt_number === "number" && Number.isFinite(d.attempt_number)
          ? d.attempt_number
          : 0,
      patch_applied: Boolean(d.patch_applied),
      error: typeof d.error === "string" ? d.error : null,
      timestamp: typeof d.timestamp === "string" ? d.timestamp : "",
      steps: parsedSteps,
      verdict: parseValidationAttemptVerdict(d.verdict),
    });
  }
  return result;
}

function parseValidationAttemptVerdict(
  value: unknown,
): ValidationAttemptSummary["verdict"] {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  return {
    is_accepted: Boolean(d.is_accepted),
    confidence: typeof d.confidence === "string" ? d.confidence : "low",
    reason: typeof d.reason === "string" ? d.reason : "",
    gates_passed: Array.isArray(d.gates_passed)
      ? d.gates_passed.filter((g): g is string => typeof g === "string")
      : [],
    gates_failed: Array.isArray(d.gates_failed)
      ? d.gates_failed.filter((g): g is string => typeof g === "string")
      : [],
    benchmark_comparison: parseValidationBenchmarkComparison(d.benchmark_comparison),
  };
}

function parseValidationBenchmarkComparison(
  value: unknown,
): ValidationBenchmarkSummary | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  const required = [
    "improvement_pct",
    "baseline_duration_seconds",
    "candidate_duration_seconds",
  ] as const;
  if (!required.every((k) => typeof d[k] === "number" && Number.isFinite(d[k] as number))) {
    return null;
  }
  return {
    improvement_pct: d.improvement_pct as number,
    passes_threshold: Boolean(d.passes_threshold),
    is_significant: Boolean(d.is_significant),
    baseline_duration_seconds: d.baseline_duration_seconds as number,
    candidate_duration_seconds: d.candidate_duration_seconds as number,
  };
}

function parseThinkingTrace(value: unknown): ThinkingTrace | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  if (
    typeof d.model !== "string" ||
    typeof d.provider !== "string" ||
    typeof d.reasoning !== "string" ||
    typeof d.prompt_tokens !== "number" ||
    typeof d.completion_tokens !== "number" ||
    typeof d.tokens_used !== "number" ||
    typeof d.timestamp !== "string"
  ) {
    return null;
  }
  return {
    model: d.model,
    provider: d.provider,
    reasoning: d.reasoning,
    prompt_tokens: d.prompt_tokens,
    completion_tokens: d.completion_tokens,
    tokens_used: d.tokens_used,
    timestamp: d.timestamp,
  };
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

function shortenPath(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 2) return path;
  return `…/${parts.slice(-2).join("/")}`;
}

/**
 * Renders text that may contain backtick-delimited code spans.
 * Short code spans (≤50 chars) render inline; longer ones are promoted to
 * their own block <pre> so they read like code in an IDE rather than
 * awkward inline blobs inside a sentence.
 */
function RichText({ text }: { text: string }) {
  const parts = text.split(/(`[^`\n]+`)/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
          const code = part.slice(1, -1);
          if (code.length > 50) {
            return (
              <pre
                key={i}
                className="mt-1.5 mb-1 rounded bg-white/[0.05] px-3 py-2 text-[11px] font-mono text-emerald-300/80 whitespace-pre-wrap break-all"
              >
                {code}
              </pre>
            );
          }
          return (
            <code
              key={i}
              className="font-mono text-emerald-300/80 bg-white/[0.06] rounded px-1 py-0.5 text-[11px] break-all"
            >
              {code}
            </code>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}
