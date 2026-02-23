import type { ThinkingTrace } from "@/lib/types";

export function PatchReasoningPanel({ trace }: { trace: ThinkingTrace }) {
  const providerLabels: Record<string, string> = {
    anthropic: "Claude",
    openai: "GPT",
    google: "Gemini",
  };
  const label = providerLabels[trace.provider] ?? trace.provider;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/30">
          {label} · {trace.model}
        </span>
        <span
          className="text-xs text-white/25"
          title={`${trace.prompt_tokens} prompt + ${trace.completion_tokens} completion`}
        >
          {(trace.prompt_tokens + trace.completion_tokens).toLocaleString()} tokens
        </span>
      </div>
      {trace.reasoning ? (
        <pre className="max-h-64 overflow-y-auto rounded-xl border border-white/8 bg-black/20 px-4 py-3 text-xs leading-relaxed text-white/70 whitespace-pre-wrap font-mono">
          {trace.reasoning}
        </pre>
      ) : (
        <p className="text-xs italic text-white/30">No reasoning captured.</p>
      )}
    </div>
  );
}
