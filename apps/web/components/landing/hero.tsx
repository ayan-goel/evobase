"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const TYPING_PHRASES = [
  "Wake up to bulletproof PRs",
  "Ship faster, break nothing",
  "Your codebase, optimized 24/7",
  "Framework-aware improvements",
  "Small fixes, big impact",
];

export function Hero() {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [displayText, setDisplayText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const currentPhrase = TYPING_PHRASES[phraseIndex];
    const typingSpeed = isDeleting ? 30 : 50;
    const pauseTime = 2000;

    if (!isDeleting && displayText === currentPhrase) {
      const timeout = setTimeout(() => setIsDeleting(true), pauseTime);
      return () => clearTimeout(timeout);
    }

    if (isDeleting && displayText === "") {
      setIsDeleting(false);
      setPhraseIndex((prev) => (prev + 1) % TYPING_PHRASES.length);
      return;
    }

    const timeout = setTimeout(() => {
      setDisplayText((prev) =>
        isDeleting
          ? prev.slice(0, -1)
          : currentPhrase.slice(0, prev.length + 1)
      );
    }, typingSpeed);

    return () => clearTimeout(timeout);
  }, [displayText, isDeleting, phraseIndex]);

  return (
    <section className="relative flex min-h-[80vh] flex-col items-center justify-center px-6 pt-36 pb-12 overflow-hidden">
      {/* Subtle radial glow */}
      <div
        className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 h-[500px] w-[800px] rounded-full opacity-[0.03]"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(255,255,255,0.5) 0%, transparent 70%)",
        }}
        aria-hidden="true"
      />

      <div className="mx-auto max-w-4xl w-full text-center">
        {/* Badge */}
        <p className="relative text-xs font-medium uppercase tracking-widest text-white/30 mb-5">
          The optimization infrastructure layer
        </p>

        {/* Headline */}
        <h1 className="relative font-semibold tracking-tight text-balance">
          <span className="block text-4xl sm:text-5xl md:text-6xl text-white leading-[1.1]">
            Your codebase,
          </span>
          <span className="block text-4xl sm:text-5xl md:text-6xl text-blue-400 leading-[1.1] mt-1">
            continuously improved
          </span>
        </h1>

        {/* Typing subheadline */}
        <div className="relative mt-6 h-8 flex items-center justify-center">
          <p className="text-lg sm:text-xl text-white/50 font-medium">
            {displayText}
            <span className="inline-block w-[2px] h-5 bg-white/50 ml-1 animate-pulse rounded-full" />
          </p>
        </div>

        {/* Value prop */}
        <p className="relative mt-5 max-w-lg mx-auto text-sm sm:text-base leading-relaxed text-white/40">
          Connect your repo once. evobase runs continuously in the background,
          discovering framework-specific optimizations, validating every patch
          against your test suite, and opening PRs you can merge with confidence.
        </p>

        {/* CTA */}
        <div className="relative mt-8">
          <Link
            href="/login"
            className="group rounded-full bg-white text-black h-12 px-8 text-sm font-semibold transition-all hover:bg-white/90 hover:shadow-[0_0_40px_rgba(255,255,255,0.15)] inline-flex items-center justify-center gap-2"
          >
            Start Optimizing
            <svg
              className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </section>
  );
}
