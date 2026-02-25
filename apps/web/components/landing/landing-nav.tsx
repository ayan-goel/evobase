"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-black/80 backdrop-blur-xl border-b border-white/[0.06]"
          : "bg-transparent"
      }`}
      aria-label="Main navigation"
    >
      <div className="mx-auto max-w-5xl flex items-center justify-between px-4 sm:px-6 h-14">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-white hover:text-white/80 transition-colors"
        >
          Coreloop
        </Link>

        <div className="flex items-center gap-6">
          <a
            href="https://github.com/ayan-goel/coreloop"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline text-xs font-medium text-white/50 hover:text-white/80 transition-colors"
          >
            GitHub
          </a>
          <Link
            href="/login"
            className="rounded-full bg-white text-black h-8 px-5 text-xs font-semibold transition-colors hover:bg-white/90 inline-flex items-center justify-center"
          >
            Sign in
          </Link>
        </div>
      </div>
    </nav>
  );
}
