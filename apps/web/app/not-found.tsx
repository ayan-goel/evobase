import Link from "next/link";

export default function NotFound() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-4"
      data-testid="not-found"
    >
      <p className="text-4xl font-semibold text-white/20">404</p>
      <p className="text-sm text-white/50">Page not found.</p>
      <Link
        href="/dashboard"
        className="mt-2 rounded-full border border-white/12 bg-white/5 px-5 py-2 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
