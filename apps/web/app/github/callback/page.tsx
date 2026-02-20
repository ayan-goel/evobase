"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState, Suspense } from "react";
import { linkInstallation } from "@/lib/api";
import { RepoPicker } from "@/components/repo-picker";

function GitHubCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawId = searchParams.get("installation_id");
  const [installationId, setInstallationId] = useState<number | null>(
    rawId ? parseInt(rawId, 10) : null,
  );
  const [manualInput, setManualInput] = useState("");
  const [linked, setLinked] = useState(false);
  const [linking, setLinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLinked = useRef(false);

  useEffect(() => {
    if (!installationId || hasLinked.current) return;
    hasLinked.current = true;
    setLinking(true);
    setError(null);

    linkInstallation(installationId)
      .then(() => setLinked(true))
      .catch((err: Error) => {
        setError(err.message ?? "Unknown error");
        hasLinked.current = false;
      })
      .finally(() => setLinking(false));
  }, [installationId]);

  function handleManualLink() {
    const id = parseInt(manualInput.trim(), 10);
    if (!id || isNaN(id)) {
      setError("Please enter a valid numeric installation ID.");
      return;
    }
    hasLinked.current = false;
    setInstallationId(id);
  }

  if (linked && installationId) {
    return (
      <div className="min-h-screen pt-24 pb-16">
        <div className="mx-auto w-full max-w-2xl px-4">
          <h1 className="text-2xl font-semibold tracking-tight mb-2">
            Select Repositories
          </h1>
          <p className="text-sm text-white/50 mb-8">
            Choose which repositories to connect to Coreloop.
          </p>
          <RepoPicker installationId={installationId} />
        </div>
      </div>
    );
  }

  if (linking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-white/50">Linking GitHub App…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        {error && (
          <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-left">
            <p className="text-sm font-medium text-red-400">
              Failed to link installation
            </p>
            <p className="mt-1 text-xs text-white/40 font-mono break-all">
              {error}
            </p>
          </div>
        )}

        {!installationId && !error && (
          <p className="text-sm text-white/40 mb-6">
            No installation ID found in the URL.
          </p>
        )}

        <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-6 text-left">
          <p className="text-sm font-medium text-white mb-1">
            Enter your GitHub App installation ID
          </p>
          <p className="text-xs text-white/40 mb-4">
            Find it in{" "}
            <a
              href="https://github.com/settings/installations"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 text-white/60 hover:text-white"
            >
              github.com/settings/installations
            </a>{" "}
            — the number at the end of the URL when you click Configure.
          </p>
          <div className="flex gap-2">
            <input
              type="number"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="e.g. 12345678"
              className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-white/25 focus:outline-none focus:border-white/30"
              onKeyDown={(e) => e.key === "Enter" && handleManualLink()}
            />
            <button
              onClick={handleManualLink}
              className="rounded-full bg-white text-black px-4 py-2 text-sm font-semibold hover:bg-white/90 transition-colors"
            >
              Link
            </button>
          </div>
        </div>

        <button
          onClick={() => router.push("/dashboard")}
          className="mt-4 text-xs text-white/30 hover:text-white/50 transition-colors"
        >
          ← Back to dashboard
        </button>
      </div>
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-sm text-white/50">Loading…</p>
        </div>
      }
    >
      <GitHubCallbackContent />
    </Suspense>
  );
}
