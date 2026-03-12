"use client";

import { useEffect, useRef, useState } from "react";

const FEATURES = [
  {
    title: "Watch the agent think in real-time",
    description:
      "Every phase streams live — clone, baseline, discovery, patching, validation. See exactly what evobase is doing at any moment.",
    visual: <LiveStreamVisual />,
  },
  {
    title: "Multiple approaches, best one wins",
    description:
      "For every opportunity, evobase generates multiple fix strategies, validates each against your tests, and picks the highest-confidence approach.",
    visual: <PatchApproachVisual />,
  },
  {
    title: "Complete reasoning transparency",
    description:
      "Understand why each change was proposed. Full chain-of-thought reasoning for discovery decisions and patch strategies.",
    visual: <ReasoningVisual />,
  },
];

export function Features() {
  return (
    <section className="px-6 py-28 sm:py-36">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-white/30 mb-4">
            Under the hood
          </p>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance text-white leading-[1.1]">
            See everything the agent does
          </h2>
          <p className="mt-6 text-lg sm:text-xl text-white/40 max-w-2xl mx-auto leading-relaxed">
            evobase is not a black box. You get full visibility into every decision.
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
      { threshold: 0.1 },
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
        <div className="flex flex-col justify-center p-10 lg:p-12">
          <h3 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white text-balance">
            {title}
          </h3>
          <p className="mt-4 text-base sm:text-lg leading-relaxed text-white/40">
            {description}
          </p>
        </div>
        <div className="border-t lg:border-t-0 lg:border-l border-white/[0.06] p-8 lg:p-10 flex items-center justify-center min-h-[320px]">
          {visual}
        </div>
      </div>
    </div>
  );
}

/* Live Stream Visual */
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
          }, 500);
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
    { phase: "clone", label: "Repository cloned", icon: "check" },
    { phase: "baseline", label: "Baseline tests passing", icon: "check" },
    { phase: "discovery", label: "Scanning utils/format.ts", icon: "pulse" },
    { phase: "discovery", label: "3 opportunities found", icon: "check" },
    { phase: "patch", label: "Generating approach 1/3", icon: "pulse" },
  ] as const;

  return (
    <div ref={ref} className="w-full max-w-sm space-y-3">
      {events.map((event, i) => (
        <div
          key={i}
          className={`flex items-center gap-4 rounded-xl border px-5 py-4 transition-all duration-500 ${
            i < activeEvents
              ? "border-white/[0.08] bg-white/[0.04] opacity-100"
              : "border-transparent opacity-0 translate-y-3"
          }`}
        >
          {event.icon === "check" ? (
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/15">
              <svg className="h-3.5 w-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </span>
          ) : (
            <span className="flex h-6 w-6 shrink-0 items-center justify-center">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-400" />
              </span>
            </span>
          )}
          <span className="text-sm text-white/60 font-mono truncate">{event.label}</span>
          <span className="ml-auto text-xs text-white/20 uppercase tracking-wider shrink-0">
            {event.phase}
          </span>
        </div>
      ))}
    </div>
  );
}

/* Patch Approaches Visual */
function PatchApproachVisual() {
  return (
    <div className="w-full max-w-sm space-y-3">
      {[
        { label: "Memoize computation", confidence: "high", selected: true },
        { label: "Lazy initialization", confidence: "medium", selected: false },
        { label: "Cache with WeakMap", confidence: "low", selected: false },
      ].map((approach, i) => (
        <div
          key={i}
          className={`flex items-center gap-4 rounded-xl border px-5 py-4 ${
            approach.selected
              ? "border-emerald-500/20 bg-emerald-500/[0.06]"
              : "border-white/[0.06] bg-white/[0.02]"
          }`}
        >
          <div className="flex-1 min-w-0">
            <p className={`text-sm font-medium ${approach.selected ? "text-emerald-300" : "text-white/60"}`}>
              {approach.label}
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${
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
            <svg className="h-5 w-5 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      ))}
    </div>
  );
}

/* Reasoning Visual */
function ReasoningVisual() {
  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] overflow-hidden">
        <div className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full border border-violet-500/30 bg-violet-500/15">
            <span className="text-xs" aria-hidden="true">{"✦"}</span>
          </div>
          <span className="text-sm font-medium text-white/60">Agent reasoning</span>
        </div>
        <div className="p-5">
          <pre className="text-sm leading-relaxed text-white/40 whitespace-pre-wrap font-mono">
            {`This function recalculates
the full dataset on every
render. Memoizing with useMemo
eliminates redundant work and
improves performance by ~40%.`}
          </pre>
        </div>
      </div>
    </div>
  );
}
