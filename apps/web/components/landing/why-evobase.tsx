"use client";

import { useEffect, useRef, useState } from "react";

const COMPARISONS = [
  {
    problem: "AI coding assistants require you to be in the loop",
    solution: "evobase runs 24/7 autonomously — you focus on features, it handles code health",
  },
  {
    problem: "Manual code review catches issues after they're written",
    solution: "Continuous optimization prevents issues before they compound",
  },
  {
    problem: "Generic suggestions that don't know your stack",
    solution: "Framework-specific fixes for React, Next.js, Express, FastAPI, and more",
  },
  {
    problem: "Large refactors that are risky to merge",
    solution: "Small, surgical patches that are easy to review and merge confidently",
  },
];

const VALUE_PROPS = [
  {
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: "Set it and forget it",
    description: "Configure once, then let evobase work in the background. Come back to a queue of validated, mergeable PRs.",
  },
  {
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
    title: "Bulletproof patches",
    description: "Every change runs through your full test suite and build. Zero regressions, guaranteed.",
  },
  {
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    title: "Small, fast improvements",
    description: "Not huge refactors — targeted fixes that improve performance, maintainability, and best practices.",
  },
  {
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    title: "Full transparency",
    description: "See exactly why each change was proposed. Complete reasoning, diffs, and validation results.",
  },
];

export function WhyEvobase() {
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
    <section ref={ref} className="px-6 py-20 sm:py-24">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-balance text-white leading-[1.1]">
            You build the product.
          </h2>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-balance text-white/35 leading-[1.1] mt-1">
            evobase bulletproofs the code.
          </h2>
          <p className="mt-6 text-base sm:text-lg text-white/40 max-w-xl mx-auto leading-relaxed">
            Unlike coding assistants that wait for your prompts, evobase works autonomously
            — discovering and fixing issues while you focus on shipping features.
          </p>
        </div>

        {/* Value props grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-14">
          {VALUE_PROPS.map((prop, i) => (
            <div
              key={prop.title}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 transition-all duration-700"
              style={{
                opacity: isVisible ? 1 : 0,
                transform: isVisible ? "translateY(0)" : "translateY(20px)",
                transitionDelay: `${i * 100}ms`,
              }}
            >
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-white/60">
                  {prop.icon}
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">{prop.title}</h3>
                  <p className="mt-1.5 text-sm text-white/40 leading-relaxed">{prop.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Comparison section */}
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
          <div className="border-b border-white/[0.06] px-6 py-4">
            <p className="text-xs font-medium text-white/50 uppercase tracking-wider">
              Why evobase over manual AI tools
            </p>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {COMPARISONS.map((item, i) => (
              <div
                key={i}
                className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-6 transition-all duration-700"
                style={{
                  opacity: isVisible ? 1 : 0,
                  transitionDelay: `${(i + 4) * 100}ms`,
                }}
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-400 mt-0.5">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </span>
                  <p className="text-sm text-white/40">{item.problem}</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 mt-0.5">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                  <p className="text-sm text-white/60">{item.solution}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
