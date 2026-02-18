import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <main className="mx-auto w-full max-w-3xl px-4 text-center">
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-8 sm:p-12">
          <h1 className="text-[clamp(2rem,6vw,4.5rem)] leading-[1.05] tracking-tight text-balance font-semibold">
            Coreloop
          </h1>
          <p className="mt-4 text-sm sm:text-base leading-relaxed text-white/70">
            Autonomous code optimization system. Connect your repo, come back
            later, review real improvements.
          </p>
          <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/login"
              className="rounded-full bg-white text-black h-10 sm:h-11 px-6 sm:px-10 text-sm font-semibold transition-colors hover:bg-white/90 inline-flex items-center justify-center"
            >
              Get Started
            </Link>
            <a
              href="https://github.com/ayan-goel/coreloop"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full bg-transparent border border-white/[0.10] text-white h-10 sm:h-11 px-6 sm:px-10 text-sm font-medium transition-colors hover:bg-white/[0.06] hover:border-white/[0.16] inline-flex items-center justify-center"
            >
              View on GitHub
            </a>
          </div>
        </div>
      </main>
    </div>
  );
}
