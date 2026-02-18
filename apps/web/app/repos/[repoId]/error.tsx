"use client";

export default function RepoError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      className="min-h-screen pt-24 flex flex-col items-center justify-center gap-4"
      data-testid="repo-error"
    >
      <p className="text-sm text-white/50">Something went wrong.</p>
      {error.message && (
        <p className="text-xs text-white/30 max-w-sm text-center">{error.message}</p>
      )}
      <button
        onClick={reset}
        className="mt-2 rounded-full border border-white/12 bg-white/5 px-5 py-2 text-xs font-medium text-white/60 transition-colors hover:bg-white/10 hover:text-white/80"
      >
        Try again
      </button>
    </div>
  );
}
