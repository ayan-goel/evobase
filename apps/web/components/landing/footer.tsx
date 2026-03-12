import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-white/[0.04] px-6 py-8">
      <div className="mx-auto max-w-4xl flex flex-col sm:flex-row items-center justify-between gap-3">
        <Link
          href="/"
          className="text-sm font-semibold text-white/60 hover:text-white/80 transition-colors"
        >
          evobase
        </Link>
        <p className="text-xs text-white/25">
          Continuous code optimization, fully autonomous.
        </p>
      </div>
    </footer>
  );
}
