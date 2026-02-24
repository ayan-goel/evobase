import { cn } from "@/lib/utils";

interface DiffViewerProps {
  diff: string;
  className?: string;
}

type DiffLineKind = "header" | "hunk" | "addition" | "deletion" | "context";

interface DiffLine {
  kind: DiffLineKind;
  content: string;
}

/** Parse a unified diff string into typed lines for rendering. */
function parseDiff(diff: string): DiffLine[] {
  return diff.split("\n").map((line): DiffLine => {
    if (line.startsWith("--- ") || line.startsWith("+++ "))
      return { kind: "header", content: line };
    if (line.startsWith("@@"))
      return { kind: "hunk", content: line };
    if (line.startsWith("+"))
      return { kind: "addition", content: line };
    if (line.startsWith("-"))
      return { kind: "deletion", content: line };
    return { kind: "context", content: line };
  });
}

const LINE_STYLES: Record<DiffLineKind, string> = {
  header: "text-white/40 bg-transparent",
  hunk: "text-blue-300/80 bg-blue-500/[0.04]",
  addition: "text-emerald-300 bg-emerald-500/[0.06]",
  deletion: "text-red-300 bg-red-500/[0.06]",
  context: "text-white/50",
};

/**
 * Renders a unified diff string as a side-scrollable code block with
 * green additions, red deletions, and dimmed context lines.
 */
export function DiffViewer({ diff, className }: DiffViewerProps) {
  const lines = parseDiff(diff);

  if (!diff.trim()) {
    return (
      <div
        className={cn(
          "rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-sm text-white/40",
          className,
        )}
      >
        No diff available.
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border border-white/[0.06] bg-white/[0.02]",
        className,
      )}
      role="region"
      aria-label="Code diff"
    >
      <pre className="text-xs leading-5 font-mono p-4 whitespace-pre-wrap break-all overflow-hidden">
        {lines.map((line, i) => (
          <span
            key={i}
            className={cn("block px-2 -mx-2 rounded-sm", LINE_STYLES[line.kind])}
          >
            {line.content || " "}
          </span>
        ))}
      </pre>
    </div>
  );
}
