import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/[0.06] px-4 py-6">
      <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-sm font-semibold tracking-tight text-white/60 hover:text-white/80 transition-colors"
          >
            evobase
          </Link>
          <span className="text-xs text-white/20">
            Autonomous code optimization
          </span>
        </div>

        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="text-xs text-white/30 hover:text-white/60 transition-colors"
          >
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}
