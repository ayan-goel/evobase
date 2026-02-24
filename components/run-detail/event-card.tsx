"use client";

import type { ReactElement } from "react";
import { memo, useState } from "react";
import { DiffViewer } from "@/components/diff-viewer";
import { PatchReasoningPanel } from "@/components/patch-reasoning-panel";
import {
  failureReason: string | null;
}

export const EventCard = memo(function EventCard({ event }: EventCardProps) {
  const renderer = EVENT_RENDERERS[event.type] ?? renderGeneric;
  return renderer(event);
});

// ---------------------------------------------------------------------------
// Per-event-type renderers
