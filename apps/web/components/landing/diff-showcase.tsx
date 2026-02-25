"use client";

import { useEffect, useRef, useState } from "react";

const DIFF_LINES = [
  { type: "header", content: "--- a/utils/format.ts" },
  { type: "header", content: "+++ b/utils/format.ts" },
  { type: "hunk", content: "@@ -12,8 +12,6 @@" },
  { type: "deletion", content: "-  const result = data.map(item => {" },
  { type: "deletion", content: "-    return expensiveTransform(item);" },
  { type: "deletion", content: "-  });" },
  { type: "addition", content: "+  const result = useMemo(" },
  { type: "addition", content: "+    () => data.map(expensiveTransform)," },
  { type: "addition", content: "+    [data]" },
  { type: "addition", content: "+  );" },
  { type: "context", content: "   return result;" },
] as const;

const LINE_STYLES: Record<string, string> = {
  header: "text-white/30",
  hunk: "text-blue-300/60",
  addition: "text-emerald-300 bg-emerald-500/[0.06]",
  deletion: "text-red-300 bg-red-500/[0.06]",
  context: "text-white/40",
};

export function DiffShowcase() {
  const ref = useRef<HTMLDivElement>(null);
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          const interval = setInterval(() => {
            setVisibleLines((prev) => {
              if (prev >= DIFF_LINES.length) {
                clearInterval(interval);
                return DIFF_LINES.length;
              }
              return prev + 1;
            });
          }, 150);
          observer.disconnect();
          return () => clearInterval(interval);
        }
      },
      { threshold: 0.3 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={ref} className="px-4 py-24 sm:py-32">
      <div className="mx-auto max-w-5xl">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          {/* Left: Text */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-emerald-400/80 mb-4">
              Code quality
            </p>
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-balance text-white">
              Real improvements, not busywork
            </h2>
            <p className="mt-4 text-base text-white/45 leading-relaxed">
              Every patch is validated against your full build and test suite.
              Coreloop only proposes changes that pass every gate — no broken
              builds, no flaky tests, no regressions.
            </p>

            {/* Stats */}
            <div className="mt-8 grid grid-cols-3 gap-6">
              {[
                { value: "100%", label: "Tests pass" },
                { value: "0", label: "Regressions" },
                { value: "High", label: "Confidence" },
              ].map((stat) => (
                <div key={stat.label}>
                  <p className="text-2xl font-semibold text-white">{stat.value}</p>
                  <p className="mt-1 text-xs text-white/35">{stat.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Animated Diff */}
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] overflow-hidden">
            {/* Diff header bar */}
            <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-white/10" aria-hidden="true" />
              <span className="h-3 w-3 rounded-full bg-white/10" aria-hidden="true" />
              <span className="h-3 w-3 rounded-full bg-white/10" aria-hidden="true" />
              <span className="ml-3 text-xs text-white/30 font-mono">utils/format.ts</span>
              <span className="ml-auto flex items-center gap-1.5 text-xs font-mono">
                <span className="text-emerald-400">+4</span>
                <span className="text-red-400">-3</span>
              </span>
            </div>
            {/* Diff body */}
            <pre className="p-4 text-xs leading-6 font-mono">
              {DIFF_LINES.map((line, i) => (
                <span
                  key={i}
                  className={`block px-2 -mx-2 rounded-sm transition-all duration-300 ${LINE_STYLES[line.type]} ${
                    i < visibleLines
                      ? "opacity-100 translate-y-0"
                      : "opacity-0 translate-y-1"
                  }`}
                >
                  {line.content}
                </span>
              ))}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
