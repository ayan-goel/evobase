export default function DashboardLoading() {
  return (
    <div className="min-h-screen pt-24 pb-16" data-testid="dashboard-loading">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Header skeleton */}
        <div className="mb-8 flex items-center justify-between">
          <div className="h-8 w-40 rounded-xl bg-white/[0.05] animate-pulse" />
          <div className="h-8 w-44 rounded-full bg-white/[0.05] animate-pulse" />
        </div>

        {/* Repo card skeletons */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 space-y-3"
              data-testid="repo-card-skeleton"
            >
              <div className="h-4 w-3/4 rounded-lg bg-white/[0.05] animate-pulse" />
              <div className="h-3 w-1/2 rounded-lg bg-white/[0.05] animate-pulse" />
              <div className="h-3 w-1/3 rounded-lg bg-white/[0.05] animate-pulse" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
