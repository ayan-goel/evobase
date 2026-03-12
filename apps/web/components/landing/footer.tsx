import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/[0.06] px-6 py-10">
      <div className="mx-auto max-w-6xl flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-base font-semibold tracking-tight text-white/60 hover:text-white/80 transition-colors"
          >
            evobase
          </Link>
          <span className="text-sm text-white/20">
            Autonomous code optimization
          </span>
        </div>

        <div className="flex items-center gap-6">
          <Link
            href="/login"
            className="text-sm text-white/30 hover:text-white/60 transition-colors"
          >
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}
