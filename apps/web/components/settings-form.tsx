"use client";

/**
 * SettingsForm — client component for editing per-repo budget, schedule,
 * and LLM model settings.
 *
 * Renders a form with inputs for all mutable settings fields including the
 * AI model selector. On save, POSTs the changed values to the API and shows
 * inline feedback. When a repo is paused, shows a prominent warning and an
 * "Unpause" button.
 */

import { useState, useTransition } from "react";
import { updateRepoSettings } from "@/lib/api";
import type { LLMProvider } from "@/lib/api";
import type { Repository, RepoSettings } from "@/lib/types";

interface SettingsFormProps {
  repoId: string;
  initial: RepoSettings;
  llmProviders?: LLMProvider[];
  repo?: Repository | null;
}

export function SettingsForm({ repoId, initial, llmProviders = [], repo }: SettingsFormProps) {
  const [settings, setSettings] = useState<RepoSettings>(initial);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleChange(field: keyof RepoSettings, value: string | number | boolean) {
    setSaved(false);
    setError(null);
    setSettings((prev) => ({ ...prev, [field]: value }));
  }

  function handleSave() {
    startTransition(async () => {
      try {
        const updated = await updateRepoSettings(repoId, {
          compute_budget_minutes: settings.compute_budget_minutes,
          max_proposals_per_run: settings.max_proposals_per_run,
          max_candidates_per_run: settings.max_candidates_per_run,
          schedule: settings.schedule,
          paused: settings.paused,
          llm_provider: settings.llm_provider,
          llm_model: settings.llm_model,
        });
        setSettings(updated);
        setSaved(true);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save settings.");
        setSaved(false);
      }
    });
  }

  function handleUnpause() {
    startTransition(async () => {
      try {
        const updated = await updateRepoSettings(repoId, { paused: false });
        setSettings(updated);
        setSaved(true);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to unpause repo.");
      }
    });
  }

  return (
    <div className="space-y-6">
      {/* Auto-pause warning */}
      {settings.paused && (
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-yellow-400">
                Scheduled runs are paused
              </p>
              {settings.consecutive_setup_failures >= 3 && (
                <p className="mt-1 text-xs text-white/60">
                  Setup failed {settings.consecutive_setup_failures} consecutive times.
                  Check that the install command is correct.
                </p>
              )}
              {settings.consecutive_flaky_runs >= 5 && (
                <p className="mt-1 text-xs text-white/60">
                  Tests were flaky for {settings.consecutive_flaky_runs} consecutive runs.
                  The test suite may be non-deterministic.
                </p>
              )}
            </div>
            <button
              onClick={handleUnpause}
              disabled={isPending}
              className="shrink-0 rounded-full border border-yellow-500/40 bg-yellow-500/20 px-4 py-1.5 text-xs font-medium text-yellow-300 transition-colors hover:bg-yellow-500/30 disabled:opacity-50"
            >
              Unpause
            </button>
          </div>
        </div>
      )}

      {/* Failure counters (read-only info) */}
      {(settings.consecutive_setup_failures > 0 || settings.consecutive_flaky_runs > 0) && (
        <div className="rounded-xl border border-white/8 bg-white/4 px-5 py-3">
          <p className="text-xs font-medium text-white/50 uppercase tracking-wider mb-2">
            Failure counters
          </p>
          <div className="flex gap-6">
            <div>
              <span className="text-lg font-semibold text-white/80">
                {settings.consecutive_setup_failures}
              </span>
              <span className="ml-1.5 text-xs text-white/40">setup failures</span>
            </div>
            <div>
              <span className="text-lg font-semibold text-white/80">
                {settings.consecutive_flaky_runs}
              </span>
              <span className="ml-1.5 text-xs text-white/40">flaky runs</span>
            </div>
          </div>
        </div>
      )}

      {/* Detected commands (read-only) */}
      {repo &&
        (repo.install_cmd || repo.build_cmd || repo.test_cmd || repo.typecheck_cmd) && (
          <div className="space-y-3" data-testid="detected-commands">
            <p className="text-xs font-medium text-white/60 uppercase tracking-wider">
              Detected commands
            </p>
            <div className="space-y-2">
              {[
                { label: "Install", value: repo.install_cmd },
                { label: "Build", value: repo.build_cmd },
                { label: "Test", value: repo.test_cmd },
                { label: "Typecheck", value: repo.typecheck_cmd },
              ]
                .filter((c) => c.value)
                .map((c) => (
                  <div key={c.label}>
                    <p className="mb-1 text-xs text-white/40">{c.label}</p>
                    <input
                      readOnly
                      value={c.value!}
                      aria-label={`${c.label} command`}
                      className="w-full rounded-xl border border-white/8 bg-white/[0.02] px-4 py-2 text-xs font-mono text-white/60 cursor-default focus:outline-none"
                    />
                  </div>
                ))}
            </div>
          </div>
        )}

      {/* Schedule */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Schedule (cron)
        </label>
        <input
          type="text"
          value={settings.schedule}
          onChange={(e) => handleChange("schedule", e.target.value)}
          placeholder="0 2 * * *"
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
        <p className="text-xs text-white/35">
          Standard cron expression — e.g.{" "}
          <code className="text-white/55">0 2 * * *</code> = every day at 02:00 UTC
        </p>
      </div>

      {/* Compute budget */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Daily compute budget (minutes)
        </label>
        <input
          type="number"
          min={1}
          value={settings.compute_budget_minutes}
          onChange={(e) => handleChange("compute_budget_minutes", parseInt(e.target.value, 10) || 1)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
        <p className="text-xs text-white/35">
          Total estimated CPU-minutes allowed per day (runs are ~5 min each).
        </p>
      </div>

      {/* Max proposals */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Max proposals per run
        </label>
        <input
          type="number"
          min={1}
          value={settings.max_proposals_per_run}
          onChange={(e) => handleChange("max_proposals_per_run", parseInt(e.target.value, 10) || 1)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
      </div>

      {/* Max candidates */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Max candidate validations per run
        </label>
        <input
          type="number"
          min={1}
          value={settings.max_candidates_per_run}
          onChange={(e) => handleChange("max_candidates_per_run", parseInt(e.target.value, 10) || 1)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
        <p className="text-xs text-white/35">
          Total patch validation attempts allowed per run.
        </p>
      </div>

      {/* AI Model selector */}
      {llmProviders.length > 0 && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-white/60 uppercase tracking-wider mb-1.5">
              AI Provider
            </label>
            <div className="flex flex-wrap gap-2">
              {llmProviders.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => {
                    const firstModel = p.models[0]?.id ?? "";
                    handleChange("llm_provider", p.id);
                    handleChange("llm_model", firstModel);
                  }}
                  className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                    settings.llm_provider === p.id
                      ? "border-violet-500/50 bg-violet-500/20 text-violet-300"
                      : "border-white/10 bg-white/5 text-white/55 hover:bg-white/10"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Model selector for chosen provider */}
          {(() => {
            const chosenProvider = llmProviders.find((p) => p.id === settings.llm_provider);
            if (!chosenProvider) return null;
            return (
              <div>
                <label className="block text-xs font-medium text-white/60 uppercase tracking-wider mb-1.5">
                  Model
                </label>
                <select
                  value={settings.llm_model}
                  onChange={(e) => handleChange("llm_model", e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white focus:border-white/25 focus:outline-none"
                >
                  {chosenProvider.models.map((m) => (
                    <option key={m.id} value={m.id} className="bg-neutral-900">
                      {m.label} — {m.description}
                    </option>
                  ))}
                </select>
              </div>
            );
          })()}
        </div>
      )}

      {/* Pause toggle */}
      <div className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/4 px-5 py-3.5">
        <input
          type="checkbox"
          id="paused-toggle"
          checked={settings.paused}
          onChange={(e) => handleChange("paused", e.target.checked)}
          className="h-4 w-4 rounded border-white/20 bg-white/10 accent-white"
        />
        <label htmlFor="paused-toggle" className="text-sm text-white/70">
          Pause scheduled runs for this repository
        </label>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4 pt-2">
        <button
          onClick={handleSave}
          disabled={isPending}
          className="rounded-full border border-white/15 bg-white/10 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-white/15 disabled:opacity-50"
        >
          {isPending ? "Saving…" : "Save settings"}
        </button>

        {saved && (
          <span className="text-sm text-emerald-400">Settings saved.</span>
        )}
        {error && (
          <span className="text-sm text-red-400">{error}</span>
        )}
      </div>

      {/* Last run */}
      {settings.last_run_at && (
        <p className="text-xs text-white/35">
          Last scheduled run:{" "}
          {new Date(settings.last_run_at).toLocaleString("en-US", {
            dateStyle: "medium",
            timeStyle: "short",
          })}
        </p>
      )}
    </div>
  );
}
