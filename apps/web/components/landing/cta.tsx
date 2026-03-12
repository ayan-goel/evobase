import Link from "next/link";

export function CTA() {
  return (
    <section className="px-4 py-16 sm:py-20">
      <div className="mx-auto max-w-3xl text-center">
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-8 sm:p-12 relative overflow-hidden">
          {/* Subtle glow */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(255,255,255,0.5) 0%, transparent 70%)",
            }}
            aria-hidden="true"
          />

          <h2 className="relative text-2xl sm:text-3xl font-semibold tracking-tight text-white text-balance">
            Stop babysitting your codebase
          </h2>
          <p className="relative mt-3 text-sm sm:text-base text-white/40 max-w-md mx-auto">
            Connect your repo, let evobase run continuously, and wake up to
            bulletproof PRs ready to merge. You focus on building — we handle the rest.
          </p>

          <div className="relative mt-6">
            <Link
              href="/login"
              className="group rounded-full bg-white text-black h-11 px-8 text-sm font-semibold transition-all hover:bg-white/90 hover:shadow-[0_0_30px_rgba(255,255,255,0.15)] inline-flex items-center justify-center gap-2"
            >
              Start Optimizing
              <svg
                className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>
          </div>

          <p className="relative mt-4 text-xs text-white/25">
            Free to try. No credit card required.
          </p>
        </div>
      </div>
    </section>
  );
}
