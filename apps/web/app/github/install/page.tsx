"use client";

import { useEffect } from "react";

const GITHUB_APP_SLUG = process.env.NEXT_PUBLIC_GITHUB_APP_SLUG ?? "coreloop-dev";

export default function GitHubInstallPage() {
  useEffect(() => {
    window.location.href = `https://github.com/apps/${GITHUB_APP_SLUG}/installations/new`;
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-sm text-white/50">Redirecting to GitHub...</p>
    </div>
  );
}
