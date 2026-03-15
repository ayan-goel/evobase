export default function DashboardLoading() {
  return (
    <div className="min-h-screen pt-24 pb-16" data-testid="dashboard-loading">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Header skeleton */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <div className="h-8 w-40 rounded-xl bg-white/[0.05] animate-pulse" />
            <div className="mt-1.5 h-3 w-48 rounded bg-white/[0.05] animate-pulse" />
          </div>
          <div className="h-9 w-44 rounded-full bg-white/[0.05] animate-pulse shrink-0" />
        </div>

        {/* Repo card skeletons */}
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 sm:p-5"
              data-testid="repo-card-skeleton"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-2 flex-1 min-w-0">
                  <div className="h-4 w-3/4 rounded-lg bg-white/[0.05] animate-pulse" />
                  <div className="h-3 w-1/2 rounded-lg bg-white/[0.05] animate-pulse" />
                  <div className="mt-1.5 h-3 w-1/3 rounded-lg bg-white/[0.05] animate-pulse" />
                </div>
                <div className="h-5 w-16 rounded-full bg-white/[0.05] animate-pulse shrink-0" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
