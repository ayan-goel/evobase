"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

interface NavUser {
  avatar_url?: string;
  github_login?: string;
}

interface NavProps {
  user?: NavUser | null;
}

/** Glassy floating navigation bar shared across dashboard pages. */
export function Nav({ user }: NavProps) {
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <nav
      className="fixed top-4 left-1/2 z-50 -translate-x-1/2 w-[calc(100%-2rem)] max-w-2xl"
      aria-label="Main navigation"
    >
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.04] backdrop-blur-xl">
        {/* Main bar */}
        <div className="flex items-center justify-between px-5 py-2.5">
          <Link
            href="/dashboard"
            className="text-sm font-semibold tracking-tight text-white hover:text-white/80 transition-colors"
          >
            Coreloop
          </Link>

          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="hidden sm:inline text-xs font-medium text-white/60 hover:text-white/90 transition-colors"
            >
              Dashboard
            </Link>

            {user ? (
              <div className="hidden sm:flex items-center gap-3">
                {user.avatar_url && (
                  <img
                    src={user.avatar_url}
                    alt={user.github_login ?? "User avatar"}
                    className="h-6 w-6 rounded-full ring-1 ring-white/10"
                  />
                )}
                {user.github_login && (
                  <span className="text-xs text-white/60">
                    {user.github_login}
                  </span>
                )}
                <button
                  onClick={handleSignOut}
                  className="text-xs font-medium text-white/50 hover:text-white/80 transition-colors"
                >
                  Sign out
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                className="hidden sm:inline text-xs font-medium text-white/60 hover:text-white/90 transition-colors"
              >
                Sign in
              </Link>
            )}

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMobileOpen((o) => !o)}
              aria-label="Toggle menu"
              aria-expanded={mobileOpen}
              className="sm:hidden flex items-center justify-center h-7 w-7 rounded-full border border-white/10 text-white/60 hover:text-white/80 transition-colors"
            >
              {mobileOpen ? (
                <span className="text-sm leading-none">✕</span>
              ) : (
                <span className="text-sm leading-none">☰</span>
              )}
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {mobileOpen && (
          <div
            className="sm:hidden border-t border-white/[0.06] px-5 py-4 flex flex-col gap-3"
            data-testid="mobile-menu"
          >
            <Link
              href="/dashboard"
              onClick={() => setMobileOpen(false)}
              className="text-sm font-medium text-white/70 hover:text-white transition-colors"
            >
              Dashboard
            </Link>

            {user ? (
              <>
                {user.github_login && (
                  <span className="text-xs text-white/40">{user.github_login}</span>
                )}
                <button
                  onClick={() => { setMobileOpen(false); handleSignOut(); }}
                  className="text-left text-sm font-medium text-white/50 hover:text-white/80 transition-colors"
                >
                  Sign out
                </button>
              </>
            ) : (
              <Link
                href="/login"
                onClick={() => setMobileOpen(false)}
                className="text-sm font-medium text-white/70 hover:text-white transition-colors"
              >
                Sign in
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
