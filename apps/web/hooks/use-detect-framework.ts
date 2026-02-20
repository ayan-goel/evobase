"use client";

import { useEffect, useState } from "react";
import { detectFramework, type DetectFrameworkResult } from "@/lib/api";

/**
 * Debounced hook that calls /repos/detect-framework whenever the selected
 * repo or root_dir changes.
 *
 * Pass null for repoFullName to disable detection (e.g. no repo selected yet).
 * The 500ms debounce prevents a call on every keystroke while the user types
 * a root_dir path.
 */
export function useDetectFramework(
  installationId: number,
  repoFullName: string | null,
  rootDir: string,
) {
  const [result, setResult] = useState<DetectFrameworkResult | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);

  useEffect(() => {
    if (!repoFullName) {
      setResult(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsDetecting(true);
      try {
        const detection = await detectFramework(
          installationId,
          repoFullName,
          rootDir || null,
        );
        setResult(detection);
      } catch {
        setResult(null);
      } finally {
        setIsDetecting(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [installationId, repoFullName, rootDir]);

  return { result, isDetecting };
}
