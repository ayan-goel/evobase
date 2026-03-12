"use client";

import { useEffect, useRef, useState } from "react";

const PHASES = [
  {
    key: "connect",
    label: "Connect",
    description: "Link your GitHub repo with one click. evobase clones and analyzes your codebase.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.939-2.052a4.5 4.5 0 00-1.242-7.244l-4.5-4.5a4.5 4.5 0 00-6.364 6.364l1.757 1.757" />
      </svg>
    ),
  },
  {
    key: "discover",
    label: "Discover",
    description: "AI scans every file for framework-specific optimization opportunities unique to your stack.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    key: "patch",
    label: "Patch",
    description: "Generates multiple approaches per opportunity and selects the highest-confidence fix.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    ),
  },
  {
    key: "validate",
    label: "Validate",
    description: "Runs your full test suite and build. Only patches that pass every gate move forward.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    key: "ship",
    label: "Ship",
    description: "Opens a PR with the diff, reasoning, and confidence — ready for you to review and merge.",
    icon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
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
            setTimeout(() => setActiveIndex(i), i * 300);
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
    <section ref={sectionRef} className="px-6 py-28 sm:py-36">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-emerald-400/80 mb-4">
            How it works
          </p>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-balance text-white leading-[1.1]">
            Five steps. Fully autonomous.
          </h2>
          <p className="mt-6 text-lg sm:text-xl text-white/40 max-w-2xl mx-auto leading-relaxed">
            You connect the repo and walk away. evobase handles everything else.
          </p>
        </div>

        {/* Pipeline steps */}
        <div className="relative">
          {/* Connecting line - desktop */}
          <div
            className="absolute top-8 left-0 right-0 h-px bg-white/[0.06] hidden lg:block"
            style={{ left: "10%", right: "10%" }}
            aria-hidden="true"
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
            {PHASES.map((phase, i) => {
              const isActive = i <= activeIndex;
              return (
                <div
                  key={phase.key}
                  className={`relative rounded-2xl border p-6 transition-all duration-500 ${
                    isActive
                      ? "border-white/[0.10] bg-white/[0.04]"
                      : "border-transparent bg-white/[0.02]"
                  }`}
                  style={{
                    opacity: isActive ? 1 : 0.3,
                    transform: isActive ? "translateY(0)" : "translateY(12px)",
                    transition: "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
                  }}
                >
                  {/* Step indicator */}
                  <div
                    className={`relative z-10 flex h-14 w-14 items-center justify-center rounded-xl border transition-all duration-500 mb-5 ${
                      isActive
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                        : "border-white/[0.08] bg-white/[0.03] text-white/30"
                    }`}
                  >
                    {phase.icon}
                  </div>

                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-xs font-mono text-white/20">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="text-lg font-semibold text-white">
                      {phase.label}
                    </h3>
                  </div>
                  <p className="text-sm text-white/40 leading-relaxed">
                    {phase.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
