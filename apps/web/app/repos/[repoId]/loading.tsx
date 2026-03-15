export default function RepoLoading() {
  return (
    <div className="min-h-screen pt-24 pb-16" data-testid="repo-loading">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Breadcrumb skeleton */}
        <div className="mb-6 h-3 w-40 rounded bg-white/[0.05] animate-pulse" />

        {/* Repo header skeleton */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <div className="h-8 w-64 rounded-xl bg-white/[0.05] animate-pulse" />
            <div className="mt-1.5 h-4 w-40 rounded bg-white/[0.05] animate-pulse" />
          </div>
          <div className="h-8 w-24 rounded-lg bg-white/[0.05] animate-pulse shrink-0" />
        </div>

        {/* TriggerRunButton placeholder */}
        <div className="mb-6 h-8 w-28 rounded-lg bg-white/[0.05] animate-pulse" />

        {/* Run list skeleton */}
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-5 py-4"
              data-testid="run-skeleton"
            >
              {/* Header row inside card */}
              <div className="flex items-center gap-3">
                <div className="h-5 w-20 rounded-full bg-white/[0.05] animate-pulse" />
                <div className="h-3 w-24 rounded bg-white/[0.05] animate-pulse" />
                <div className="h-3 w-16 rounded bg-white/[0.05] animate-pulse" />
              </div>
              {/* Proposal cards grid */}
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="h-28 rounded-xl bg-white/[0.05] animate-pulse" />
                <div className="h-28 rounded-xl bg-white/[0.05] animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
