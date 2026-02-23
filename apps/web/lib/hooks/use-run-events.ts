"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getRunEventsUrl } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { RunEvent, RunPhase } from "@/lib/types";

interface UseRunEventsResult {
  events: RunEvent[];
  currentPhase: RunPhase | null;
  isConnected: boolean;
  isDone: boolean;
}

const PHASE_ORDER: RunPhase[] = [
  "clone",
  "detection",
  "baseline",
  "discovery",
  "patching",
  "validation",
  "selection",
  "run",
];

export function useRunEvents(
  runId: string,
  isActive: boolean,
): UseRunEventsResult {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string>("0");
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    setEvents([]);
    setIsConnected(false);
    setIsDone(false);
    lastEventIdRef.current = "0";
    seenEventIdsRef.current = new Set();
  }, [runId]);

  const connect = useCallback(async () => {
    if (isDone) return;

    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;

    const url = new URL(getRunEventsUrl(runId));
    if (token) url.searchParams.set("token", token);

    const es = new EventSource(url.toString());
    eventSourceRef.current = es;

    es.onopen = () => setIsConnected(true);

    es.addEventListener("run_event", (e: MessageEvent) => {
      try {
        const event: RunEvent = JSON.parse(e.data);
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId;
        if (event.id && seenEventIdsRef.current.has(event.id)) {
          return;
        }
        if (event.id) {
          seenEventIdsRef.current.add(event.id);
        }
        setEvents((prev) => [...prev, event]);
      } catch {
        // Ignore parse errors
      }
    });

    es.addEventListener("done", () => {
      setIsDone(true);
      es.close();
      setIsConnected(false);
    });

    es.onerror = () => {
      setIsConnected(false);
      es.close();
      // Only auto-reconnect for active runs; completed runs read from Redis once.
      if (isActive && !isDone) {
        setTimeout(() => connect(), 3000);
      }
    };
  }, [runId, isActive, isDone]);

  useEffect(() => {
    if (!isDone) {
      connect();
    }

    return () => {
      eventSourceRef.current?.close();
      setIsConnected(false);
    };
  }, [connect, isDone]);

  const currentPhase = events.length > 0
    ? events[events.length - 1].phase as RunPhase
    : null;

  return { events, currentPhase, isConnected, isDone };
}
