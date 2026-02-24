"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { getRun } from "@/lib/api";
import { useRunEvents } from "@/lib/hooks/use-run-events";
import { CancelRunButton } from "@/components/run-detail/cancel-run-button";
// Sidebar sub-components
// ---------------------------------------------------------------------------

const PhaseIcon = memo(function PhaseIcon({
  done,
  active,
  pending,
  return (
    <span className="h-4 w-4 shrink-0 rounded-full border border-white/[0.15] bg-transparent" />
  );
});

function StatRow({
  label,
  );
}

const StatRow = memo(function StatRow({
  label,
  value,
  accent,
      </span>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Helpers
