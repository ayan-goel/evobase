"use client";

/**
 * AgentReasoning — collapsible panel showing an LLM agent's thinking trace.
 *
 * Surfaces the model's complete reasoning so the developer can see exactly
 * how the agent decided to flag this opportunity and generate this patch.
 *
 * Each ThinkingTrace includes:
 *   - Which model and provider produced it
 *   - The full reasoning / chain-of-thought text
 *   - Token usage (prompt + completion)
 */

import { useState } from "react";
import type { ThinkingTrace } from "@/lib/types";

interface AgentReasoningProps {
  discoveryTrace: ThinkingTrace | null;
  patchTrace: ThinkingTrace | null;
  /** Optional label override for the panel header */
  label?: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Claude",
  openai: "GPT",
  google: "Gemini",
};

export function AgentReasoning({
  discoveryTrace,
  patchTrace,
  label = "Agent reasoning",
}: AgentReasoningProps) {
  const [expanded, setExpanded] = useState(false);

  const hasContent = discoveryTrace || patchTrace;
  if (!hasContent) return null;

  // Use whichever trace is available for the header badge
  const primaryTrace = discoveryTrace ?? patchTrace;
  const providerLabel = PROVIDER_LABELS[primaryTrace?.provider ?? ""] ?? primaryTrace?.provider;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3">
          {/* Animated brain/spark icon */}
          <div className="flex h-7 w-7 items-center justify-center rounded-full border border-violet-500/30 bg-violet-500/15">
            <span className="text-xs" aria-hidden="true">
              ✦
            </span>
          </div>
          <span className="text-sm font-medium text-white/80">{label}</span>
          {primaryTrace && (
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs text-white/50">
              {providerLabel} · {primaryTrace.model}
            </span>
          )}
        </div>
        <ChevronIcon expanded={expanded} />
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-white/8 px-5 pb-5 pt-4 space-y-5">
          {discoveryTrace && (
            <TraceSection
              title="Discovery reasoning"
              subtitle="Why this opportunity was identified"
              trace={discoveryTrace}
            />
          )}
          {patchTrace && (
            <TraceSection
              title="Patch generation reasoning"
              subtitle="How the agent decided on this specific change"
              trace={patchTrace}
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface TraceSectionProps {
  title: string;
  subtitle: string;
  trace: ThinkingTrace;
}

function TraceSection({ title, subtitle, trace }: TraceSectionProps) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-white/50">
            {title}
          </p>
          <p className="text-xs text-white/35">{subtitle}</p>
        </div>
        <TokenBadge promptTokens={trace.prompt_tokens} completionTokens={trace.completion_tokens} />
      </div>

      {trace.reasoning ? (
        <pre className="max-h-72 overflow-y-auto rounded-xl border border-white/8 bg-black/20 px-4 py-3 text-xs leading-relaxed text-white/70 whitespace-pre-wrap font-mono">
          {trace.reasoning}
        </pre>
      ) : (
        <p className="text-xs italic text-white/30">No reasoning captured for this step.</p>
      )}

      <p className="mt-1.5 text-xs text-white/25">
        {new Date(trace.timestamp).toLocaleString("en-US", {
          dateStyle: "medium",
          timeStyle: "short",
        })}
      </p>
    </div>
  );
}

function TokenBadge({
  promptTokens,
  completionTokens,
}: {
  promptTokens: number;
  completionTokens: number;
}) {
  const total = promptTokens + completionTokens;
  return (
    <span className="text-xs text-white/30" title={`${promptTokens} prompt + ${completionTokens} completion`}>
      {total.toLocaleString()} tokens
    </span>
  );
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      className={`text-white/40 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
      aria-hidden="true"
    >
      <path
        d="M4 6l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
