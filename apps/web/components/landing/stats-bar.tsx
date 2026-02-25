"use client";

import { useEffect, useRef, useState } from "react";

const STATS = [
  { value: "100%", label: "Build-safe patches", description: "Every change passes your tests" },
  { value: "5 min", label: "Average setup time", description: "Connect your repo and go" },
  { value: "24/7", label: "Autonomous operation", description: "Runs while you sleep" },
  { value: "Full", label: "Reasoning visibility", description: "See every AI decision" },
];

export function StatsBar() {
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
      { threshold: 0.3 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={ref} className="px-4 py-16 sm:py-20">
      <div className="mx-auto max-w-5xl">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-px rounded-2xl border border-white/[0.06] bg-white/[0.06] overflow-hidden">
          {STATS.map((stat, i) => (
            <div
              key={stat.label}
              className="bg-black p-6 sm:p-8 transition-all duration-700"
              style={{
                opacity: isVisible ? 1 : 0,
                transform: isVisible ? "translateY(0)" : "translateY(12px)",
                transitionDelay: `${i * 100}ms`,
              }}
            >
              <p className="text-2xl sm:text-3xl font-semibold text-white tracking-tight">
                {stat.value}
              </p>
              <p className="mt-2 text-sm font-medium text-white/70">{stat.label}</p>
              <p className="mt-1 text-xs text-white/30 leading-relaxed">{stat.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
