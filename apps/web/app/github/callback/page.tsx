"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { linkInstallation, getInstallations } from "@/lib/api";
import { RepoPicker } from "@/components/repo-picker";

export default function GitHubCallbackPage() {
  const searchParams = useSearchParams();
  const installationId = searchParams.get("installation_id");
  const [linked, setLinked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!installationId) return;

    linkInstallation(parseInt(installationId, 10))
      .then(() => setLinked(true))
      .catch((err) => setError(err.message));
  }, [installationId]);

  if (!installationId) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-red-400">
          Missing installation_id parameter.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-400">Failed to link installation.</p>
          <p className="mt-1 text-xs text-white/40">{error}</p>
        </div>
      </div>
    );
  }

  if (!linked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-white/50">Linking GitHub App...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-16">
      <div className="mx-auto w-full max-w-2xl px-4">
        <h1 className="text-2xl font-semibold tracking-tight mb-2">
          Select Repositories
        </h1>
        <p className="text-sm text-white/50 mb-8">
          Choose which repositories to connect to Coreloop.
        </p>
        <RepoPicker installationId={parseInt(installationId, 10)} />
      </div>
    </div>
  );
}
