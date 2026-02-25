"use client";

import { useEffect, useRef, useState } from "react";

const FEATURES = [
  {
    title: "Real-time pipeline streaming",
    description:
      "Watch your AI agent think, discover, and patch in real time. Every phase streams live events — clone, baseline, discovery, patching, validation — so you always know exactly what's happening.",
    visual: <LiveStreamVisual />,
  },
  {
    title: "Multi-approach patch generation",
    description:
      "For every opportunity, Coreloop generates multiple code approaches, validates each against your test suite, and selects the best one based on confidence scoring and benchmark comparisons.",
    visual: <PatchApproachVisual />,
  },
  {
    title: "Full reasoning transparency",
    description:
      "See the complete chain-of-thought behind every decision. Discovery reasoning explains why an opportunity was flagged. Patch reasoning shows how the agent crafted each change.",
    visual: <ReasoningVisual />,
  },
];

export function Features() {
  return (
    <section className="px-4 py-24 sm:py-32">
      <div className="mx-auto max-w-5xl">
        <div className="mb-16 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-4">
            Built for developers
          </p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-balance text-white">
            Every detail, visible
          </h2>
          <p className="mt-4 text-base text-white/40 max-w-lg mx-auto">
            Coreloop doesn{"'"}t hide behind a black box. You get full
            observability into every decision the agent makes.
          </p>
        </div>

        <div className="space-y-6">
          {FEATURES.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureCard({
  title,
  description,
  visual,
}: {
  title: string;
  description: string;
  visual: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className="rounded-2xl border border-white/[0.06] bg-white/[0.02] overflow-hidden transition-all duration-700"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(20px)",
      }}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="flex flex-col justify-center p-8 sm:p-10 lg:p-12">
          <h3 className="text-xl sm:text-2xl font-semibold tracking-tight text-white text-balance">
            {title}
          </h3>
          <p className="mt-3 text-sm sm:text-base leading-relaxed text-white/45">
            {description}
          </p>
        </div>
        <div className="border-t lg:border-t-0 lg:border-l border-white/[0.06] p-6 sm:p-8 flex items-center justify-center min-h-[280px]">
          {visual}
        </div>
      </div>
    </div>
  );
}

/* ── Visual: Live Stream ── */
function LiveStreamVisual() {
  const [activeEvents, setActiveEvents] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          const interval = setInterval(() => {
            setActiveEvents((prev) => {
              if (prev >= 5) {
                clearInterval(interval);
                return 5;
              }
              return prev + 1;
            });
          }, 400);
          observer.disconnect();
          return () => clearInterval(interval);
        }
      },
      { threshold: 0.5 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const events = [
    { phase: "clone", label: "Repository cloned", icon: "check", color: "emerald" },
    { phase: "baseline", label: "Baseline tests passing", icon: "check", color: "emerald" },
    { phase: "discovery", label: "Scanning utils/format.ts", icon: "pulse", color: "blue" },
    { phase: "discovery", label: "3 opportunities found", icon: "check", color: "emerald" },
    { phase: "patch", label: "Generating approach 1/3", icon: "pulse", color: "blue" },
  ] as const;

  return (
    <div ref={ref} className="w-full max-w-xs space-y-2">
      {events.map((event, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2 transition-all duration-500 ${
            i < activeEvents
              ? "border-white/[0.08] bg-white/[0.04] opacity-100"
              : "border-transparent opacity-0 translate-y-2"
          }`}
        >
          {event.icon === "check" ? (
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15">
              <svg className="h-3 w-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </span>
          ) : (
            <span className="flex h-5 w-5 shrink-0 items-center justify-center">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-400" />
              </span>
            </span>
          )}
          <span className="text-xs text-white/60 font-mono truncate">{event.label}</span>
          <span className="ml-auto text-[10px] text-white/20 uppercase tracking-wider shrink-0">
            {event.phase}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── Visual: Patch Approaches ── */
function PatchApproachVisual() {
  return (
    <div className="w-full max-w-xs space-y-2">
      {[
        { label: "Memoize computation", confidence: "high", selected: true },
        { label: "Lazy initialization", confidence: "medium", selected: false },
        { label: "Cache with WeakMap", confidence: "low", selected: false },
      ].map((approach, i) => (
        <div
          key={i}
          className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
            approach.selected
              ? "border-emerald-500/20 bg-emerald-500/[0.06]"
              : "border-white/[0.06] bg-white/[0.02]"
          }`}
        >
          <div className="flex-1 min-w-0">
            <p className={`text-sm font-medium ${approach.selected ? "text-emerald-300" : "text-white/60"}`}>
              {approach.label}
            </p>
            <p className="text-xs text-white/30 mt-0.5 font-mono">
              approach {i + 1}
            </p>
          </div>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              approach.confidence === "high"
                ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                : approach.confidence === "medium"
                  ? "border border-amber-500/20 bg-amber-500/10 text-amber-400"
                  : "border border-white/10 bg-white/5 text-white/40"
            }`}
          >
            {approach.confidence}
          </span>
          {approach.selected && (
            <svg className="h-4 w-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Visual: Reasoning ── */
function ReasoningVisual() {
  return (
    <div className="w-full max-w-xs">
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
          <div className="flex h-6 w-6 items-center justify-center rounded-full border border-violet-500/30 bg-violet-500/15">
            <span className="text-[10px]" aria-hidden="true">
              {"✦"}
            </span>
          </div>
          <span className="text-xs font-medium text-white/60">Agent reasoning</span>
          <span className="ml-auto rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-white/40">
            Claude 3.5
          </span>
        </div>
        {/* Reasoning body */}
        <div className="p-4">
          <pre className="text-[11px] leading-relaxed text-white/40 whitespace-pre-wrap font-mono">
            {`The function recalculates
the full dataset on every
render. By memoizing with
useMemo and adding proper
dependency tracking, we can
eliminate redundant work...`}
          </pre>
          <div className="mt-3 flex items-center justify-between border-t border-white/[0.06] pt-3">
            <span className="text-[10px] text-white/25">1,247 tokens</span>
            <span className="text-[10px] text-white/25">2.3s</span>
          </div>
        </div>
      </div>
    </div>
  );
}
