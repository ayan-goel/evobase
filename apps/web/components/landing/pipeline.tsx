"use client";

import { useEffect, useRef, useState } from "react";

const PHASES = [
  {
    key: "connect",
    label: "Connect",
    description: "Link your GitHub repo with one click. evobase clones and analyzes your codebase.",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.939-2.052a4.5 4.5 0 00-1.242-7.244l-4.5-4.5a4.5 4.5 0 00-6.364 6.364l1.757 1.757" />
      </svg>
    ),
  },
  {
    key: "discover",
    label: "Discover",
    description: "AI scans every file for framework-specific optimization opportunities unique to your stack.",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    key: "patch",
    label: "Patch",
    description: "Generates multiple approaches per opportunity and selects the highest-confidence fix.",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    ),
  },
  {
    key: "validate",
    label: "Validate",
    description: "Runs your full test suite and build. Only patches that pass every gate move forward.",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    key: "ship",
    label: "Ship",
    description: "Opens a PR with the diff, reasoning, and confidence — ready for you to review and merge.",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
      </svg>
    ),
  },
];

export function Pipeline() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          PHASES.forEach((_, i) => {
            setTimeout(() => setActiveIndex(i), i * 200);
          });
          observer.disconnect();
        }
      },
      { threshold: 0.2 },
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={sectionRef} className="px-6 py-20 sm:py-24">
      <div className="mx-auto max-w-4xl">
        <div className="mb-12 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400/80 mb-3">
            How it works
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-balance text-white leading-[1.1]">
            Five steps. Fully autonomous.
          </h2>
          <p className="mt-4 text-base sm:text-lg text-white/40 max-w-xl mx-auto leading-relaxed">
            You connect the repo and walk away. evobase handles everything else.
          </p>
        </div>

        {/* Pipeline steps - vertical stack of horizontal cards */}
        <div className="space-y-3">
          {PHASES.map((phase, i) => {
            const isActive = i <= activeIndex;
            return (
              <div
                key={phase.key}
                className={`relative rounded-xl border p-5 transition-all duration-500 ${
                  isActive
                    ? "border-white/[0.10] bg-white/[0.04]"
                    : "border-transparent bg-white/[0.02]"
                }`}
                style={{
                  opacity: isActive ? 1 : 0.3,
                  transform: isActive ? "translateX(0)" : "translateX(-12px)",
                  transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                }}
              >
                <div className="flex items-center gap-5">
                  {/* Step number + icon */}
                  <div className="flex items-center gap-4 shrink-0">
                    <span className="text-xs font-mono text-white/20 w-5">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-lg border transition-all duration-500 ${
                        isActive
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                          : "border-white/[0.08] bg-white/[0.03] text-white/30"
                      }`}
                    >
                      {phase.icon}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-semibold text-white">
                        {phase.label}
                      </h3>
                    </div>
                    <p className="mt-1 text-sm text-white/40 leading-relaxed">
                      {phase.description}
                    </p>
                  </div>

                  {/* Status indicator */}
                  {isActive && i < activeIndex && (
                    <div className="shrink-0">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/15">
                        <svg className="h-3.5 w-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      </span>
                    </div>
                  )}
                  {isActive && i === activeIndex && (
                    <div className="shrink-0">
                      <span className="relative flex h-3 w-3">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
                        <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
