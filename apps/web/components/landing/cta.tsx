import Link from "next/link";

export function CTA() {
  return (
    <section className="px-6 py-28 sm:py-36">
      <div className="mx-auto max-w-4xl text-center">
        <div className="rounded-3xl border border-white/[0.08] bg-white/[0.03] p-12 sm:p-16 lg:p-20 relative overflow-hidden">
          {/* Subtle glow */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(255,255,255,0.5) 0%, transparent 70%)",
            }}
            aria-hidden="true"
          />

          <h2 className="relative text-3xl sm:text-4xl lg:text-5xl font-semibold tracking-tight text-white text-balance leading-[1.1]">
            Stop babysitting your codebase
          </h2>
          <p className="relative mt-6 text-lg sm:text-xl text-white/40 max-w-xl mx-auto leading-relaxed">
            Connect your repo, let evobase run continuously, and wake up to
            bulletproof PRs ready to merge. You focus on building — we handle the rest.
          </p>

          <div className="relative mt-10">
            <Link
              href="/login"
              className="group rounded-full bg-white text-black h-14 px-10 text-base font-semibold transition-all hover:bg-white/90 hover:shadow-[0_0_40px_rgba(255,255,255,0.15)] inline-flex items-center justify-center gap-2"
            >
              Start Optimizing
              <svg
                className="h-5 w-5 transition-transform group-hover:translate-x-0.5"
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

          <p className="relative mt-8 text-sm text-white/25">
            Free to try. No credit card required.
          </p>
        </div>
      </div>
    </section>
  );
}
