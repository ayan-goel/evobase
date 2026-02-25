import Link from "next/link";

export function Hero() {
  return (
    <section className="relative flex min-h-[90vh] flex-col items-center justify-center px-4 pt-20 pb-24 overflow-hidden">
      {/* Subtle radial glow */}
      <div
        className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 h-[600px] w-[800px] rounded-full opacity-[0.07]"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(255,255,255,0.4) 0%, transparent 70%)",
        }}
        aria-hidden="true"
      />

      {/* Badge */}
      <div className="relative mb-8 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-4 py-1.5">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
        </span>
        <span className="text-xs font-medium text-white/60">
          Autonomous code optimization
        </span>
      </div>

      {/* Headline */}
      <h1 className="relative text-center text-[clamp(2.5rem,7vw,5.5rem)] leading-[1.05] tracking-tight font-semibold text-balance max-w-4xl">
        <span className="text-white">Your codebase,</span>
        <br />
        <span className="text-white/40">continuously improved</span>
      </h1>

      {/* Subheadline */}
      <p className="relative mt-6 max-w-xl text-center text-base sm:text-lg leading-relaxed text-white/50">
        Coreloop is an AI agent that connects to your repo, discovers
        optimization opportunities, writes validated patches, and opens PRs
        — all while you sleep.
      </p>

      {/* CTAs */}
      <div className="relative mt-10 flex flex-col items-center gap-4 sm:flex-row">
        <Link
          href="/login"
          className="group rounded-full bg-white text-black h-12 px-8 text-sm font-semibold transition-all hover:bg-white/90 hover:shadow-[0_0_30px_rgba(255,255,255,0.15)] inline-flex items-center justify-center gap-2"
        >
          Get Started
          <svg
            className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </Link>
        <a
          href="https://github.com/ayan-goel/coreloop"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full border border-white/[0.10] bg-transparent text-white h-12 px-8 text-sm font-medium transition-all hover:bg-white/[0.06] hover:border-white/[0.16] inline-flex items-center justify-center gap-2"
        >
          <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
              clipRule="evenodd"
            />
          </svg>
          View on GitHub
        </a>
      </div>
    </section>
  );
}
