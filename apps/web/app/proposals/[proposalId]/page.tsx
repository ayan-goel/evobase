import Link from "next/link";
import { getProposal, getArtifactSignedUrl } from "@/lib/api-server";
import { NavWithUser } from "@/components/nav-server";
import { ConfidenceBadge } from "@/components/confidence-badge";
import { DiffViewer } from "@/components/diff-viewer";
import { TraceTimeline } from "@/components/trace-timeline";
import { CreatePRButton } from "@/components/create-pr-button";
import { AgentReasoning } from "@/components/agent-reasoning";
import { PatchVariants } from "@/components/patch-variants";
import type { Artifact, Metrics, Proposal, ThinkingTrace, TraceAttempt } from "@/lib/types";

export const metadata = { title: "Proposal — Coreloop" };

interface ProposalPageData {
  proposal: Proposal;
  artifactLinks: Array<{ artifact: Artifact; signedUrl: string }>;
}

/** Presentational view — tested in isolation with mock data. */
export function ProposalView({ proposal, artifactLinks }: ProposalPageData) {
  const traceAttempts = _extractTraceAttempts(proposal);

  return (
    <div className="min-h-screen pt-24 pb-16">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Breadcrumb */}
        <nav className="mb-6 text-xs text-white/40" aria-label="Breadcrumb">
          <Link href="/dashboard" className="hover:text-white/70 transition-colors">
            Dashboard
          </Link>
          <span className="mx-2">/</span>
          <Link
            href={`/repos/${proposal.repo_id}`}
            className="hover:text-white/70 transition-colors"
          >
            Repository
          </Link>
          <span className="mx-2">/</span>
          <span className="text-white/70">Proposal</span>
        </nav>

        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <ConfidenceBadge confidence={proposal.confidence} />
              {proposal.risk_score !== null && (
                <span className="text-xs text-white/40">
                  Risk {Math.round(proposal.risk_score * 100)}%
                </span>
              )}
              {proposal.approaches_tried !== null && proposal.approaches_tried > 1 && (
                <span className="rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-0.5 text-xs text-white/40">
                  Best of {proposal.approaches_tried} approaches
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-balance">
              {proposal.summary ?? "Optimization Proposal"}
            </h1>
            {proposal.selection_reason && (
              <p className="mt-2 text-xs text-white/35">
                <span className="text-white/25">Selected: </span>
                {proposal.selection_reason}
              </p>
            )}
          </div>

          <CreatePRButton
            repoId={_extractRepoId(proposal)}
            proposalId={proposal.id}
            existingPrUrl={proposal.pr_url}
          />
        </div>

        <div className="space-y-8">
          {/* Metrics comparison */}
          {(proposal.metrics_before || proposal.metrics_after) && (
            <Section title="Metrics">
              <div className="grid gap-4 sm:grid-cols-2">
                <MetricsCard label="Before" metrics={proposal.metrics_before} />
                <MetricsCard label="After" metrics={proposal.metrics_after} />
              </div>
            </Section>
          )}

          {/* Diff viewer */}
          <Section title="Diff">
            <DiffViewer diff={proposal.diff} />
          </Section>

          {/* Approach variants — shown when the agent tried multiple strategies */}
          {proposal.patch_variants && proposal.patch_variants.length > 0 && (
            <Section title={`Approaches tried (${proposal.patch_variants.length})`}>
              <PatchVariants variants={proposal.patch_variants} />
            </Section>
          )}

          {/* Agent reasoning — shown when LLM traces are present */}
          {_hasAgentReasoning(proposal) && (
            <Section title="Agent reasoning">
              <AgentReasoning
                discoveryTrace={_extractDiscoveryTrace(proposal)}
                patchTrace={_extractPatchTrace(proposal)}
              />
            </Section>
          )}

          {/* Trace timeline */}
          {traceAttempts.length > 0 && (
            <Section title="Validation trace">
              <TraceTimeline attempts={traceAttempts} />
            </Section>
          )}

          {/* Evidence links */}
          {artifactLinks.length > 0 && (
            <Section title="Evidence files">
              <div className="flex flex-wrap gap-3">
                {artifactLinks.map(({ artifact, signedUrl }) => (
                  <a
                    key={artifact.id}
                    href={signedUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-4 py-1.5 text-xs font-medium text-white/70 hover:bg-white/[0.08] hover:text-white transition-all"
                  >
                    {_artifactLabel(artifact.type)}
                  </a>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-xs font-medium text-white/40 uppercase tracking-wider mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function MetricsCard({
  label,
  metrics,
}: {
  label: string;
  metrics: Metrics | null;
}) {
  if (!metrics) {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
        <p className="text-xs font-medium text-white/40 mb-2">{label}</p>
        <p className="text-xs text-white/30">No data</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
      <p className="text-xs font-medium text-white/40 mb-3">{label}</p>
      <div className="space-y-1.5">
        {(metrics.steps ?? []).map((step) => (
          <div key={step.name} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-white/60 font-mono">
              <span
                className={
                  step.is_success
                    ? "text-emerald-400"
                    : "text-red-400"
                }
              >
                {step.is_success ? "✓" : "✗"}
              </span>
              {step.name}
            </span>
            <span className="text-white/40">{step.duration_seconds.toFixed(2)}s</span>
          </div>
        ))}
        {metrics.bench_result && (
          <div className="flex items-center justify-between text-xs pt-1 border-t border-white/[0.04]">
            <span className="text-white/50 font-mono">bench</span>
            <span className="text-white/40">
              {metrics.bench_result.duration_seconds.toFixed(3)}s
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function _extractTraceAttempts(proposal: Proposal): TraceAttempt[] {
  // The trace timeline is stored as an artifact (trace.json).
  // For MVP, we reconstruct attempts from the proposal's metrics as a
  // single-attempt summary. The full trace is available via the evidence link.
  return [];
}

function _extractRepoId(proposal: Proposal): string {
  return proposal.repo_id;
}

function _artifactLabel(type: string): string {
  const labels: Record<string, string> = {
    proposal: "proposal.json",
    diff: "diff.patch",
    trace: "trace.json",
    log: "logs.txt",
    baseline: "baseline.json",
  };
  return labels[type] ?? type;
}

function _hasAgentReasoning(proposal: Proposal): boolean {
  return !!(proposal.discovery_trace || proposal.patch_trace);
}

function _extractDiscoveryTrace(proposal: Proposal): ThinkingTrace | null {
  return proposal.discovery_trace ?? null;
}

function _extractPatchTrace(proposal: Proposal): ThinkingTrace | null {
  return proposal.patch_trace ?? null;
}

/** RSC page — fetches data then delegates to ProposalView. */
export default async function ProposalPage({
  params,
}: {
  params: Promise<{ proposalId: string }>;
}) {
  const { proposalId } = await params;

  let proposal: Proposal | null = null;
  let artifactLinks: Array<{ artifact: Artifact; signedUrl: string }> = [];

  try {
    proposal = await getProposal(proposalId);

    // Fetch signed URLs for all artifacts in parallel
    artifactLinks = (
      await Promise.allSettled(
        proposal.artifacts.map(async (artifact) => {
          const { signed_url } = await getArtifactSignedUrl(artifact.id);
          return { artifact, signedUrl: signed_url };
        }),
      )
    )
      .filter((r): r is PromiseFulfilledResult<typeof artifactLinks[0]> => r.status === "fulfilled")
      .map((r) => r.value);
  } catch {
    // API not reachable — show fallback
  }

  if (!proposal) {
    return (
      <>
        <NavWithUser />
        <div className="min-h-screen pt-24 flex items-center justify-center">
          <p className="text-sm text-white/50">Proposal not found.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <NavWithUser />
      <ProposalView proposal={proposal} artifactLinks={artifactLinks} />
    </>
  );
}
