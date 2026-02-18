export default function RepoLoading() {
  return (
    <div className="min-h-screen pt-24 pb-16" data-testid="repo-loading">
      <div className="mx-auto w-full max-w-4xl px-4">
        {/* Breadcrumb skeleton */}
        <div className="mb-6 h-3 w-40 rounded bg-white/[0.05] animate-pulse" />

        {/* Repo header skeleton */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="h-7 w-64 rounded-xl bg-white/[0.05] animate-pulse" />
            <div className="h-3 w-40 rounded bg-white/[0.05] animate-pulse" />
          </div>
          <div className="flex gap-2">
            <div className="h-8 w-24 rounded-full bg-white/[0.05] animate-pulse" />
            <div className="h-8 w-20 rounded-full bg-white/[0.05] animate-pulse" />
          </div>
        </div>

        {/* Run list skeleton */}
        <div className="space-y-8">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3" data-testid="run-skeleton">
              <div className="flex items-center gap-3">
                <div className="h-5 w-20 rounded-full bg-white/[0.05] animate-pulse" />
                <div className="h-3 w-16 rounded bg-white/[0.05] animate-pulse" />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
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
