"use client";

import type { ReactElement } from "react";
import { useState, memo } from "react";
import { DiffViewer } from "@/components/diff-viewer";
import { PatchReasoningPanel } from "@/components/patch-reasoning-panel";
import {
  );
}

const Badge = memo(function Badge({
  children,
  variant = "default",
}: {
      {children}
    </span>
  );
});

function Mono({ children }: { children: React.ReactNode }) {
  return <code className="text-xs font-mono text-white/50">{children}</code>;
