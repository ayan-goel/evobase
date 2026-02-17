import Link from "next/link";

/** Glassy floating navigation bar shared across dashboard pages. */
export function Nav() {
  return (
    <nav
      className="fixed top-4 left-1/2 z-50 -translate-x-1/2 w-[calc(100%-2rem)] max-w-2xl"
      aria-label="Main navigation"
    >
      <div className="flex items-center justify-between rounded-full border border-white/[0.08] bg-white/[0.04] px-5 py-2.5 backdrop-blur-xl">
        <Link
          href="/dashboard"
          className="text-sm font-semibold tracking-tight text-white hover:text-white/80 transition-colors"
        >
          SelfOpt
        </Link>

        <div className="hidden sm:flex items-center gap-6">
          <Link
            href="/dashboard"
            className="text-xs font-medium text-white/60 hover:text-white/90 transition-colors"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </nav>
  );
}
