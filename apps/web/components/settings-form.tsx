"use client";

/**
 * SettingsForm — client component for editing per-repo budget, schedule,
 * LLM model settings, and repository configuration (root_dir, commands).
 *
 * Renders a form with inputs for all mutable settings fields. On save,
 * PATCHes the relevant API endpoint and shows inline feedback. When a repo
 * is paused, shows a prominent warning and an "Unpause" button.
 */

import { useState, useTransition } from "react";
import { updateRepoSettings, updateRepoConfig } from "@/lib/api";
import type { LLMProvider, Repository, RepoSettings } from "@/lib/types";

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

  // Repo-level config state (root_dir + commands)
  const [rootDir, setRootDir] = useState(repo?.root_dir ?? "");
  const [installCmd, setInstallCmd] = useState(repo?.install_cmd ?? "");
  const [buildCmd, setBuildCmd] = useState(repo?.build_cmd ?? "");
  const [testCmd, setTestCmd] = useState(repo?.test_cmd ?? "");
  const [configSaved, setConfigSaved] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [isConfigPending, startConfigTransition] = useTransition();

  function handleSaveConfig() {
    startConfigTransition(async () => {
      try {
        await updateRepoConfig(repoId, {
          root_dir: rootDir.trim() || null,
          install_cmd: installCmd.trim() || null,
          build_cmd: buildCmd.trim() || null,
          test_cmd: testCmd.trim() || null,
        });
        setConfigSaved(true);
        setConfigError(null);
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : "Failed to save configuration.");
        setConfigSaved(false);
      }
    });
  }

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
          max_prs_per_day: settings.max_prs_per_day,
          max_proposals_per_run: settings.max_proposals_per_run,
          execution_mode: settings.execution_mode,
          max_strategy_attempts: settings.max_strategy_attempts,
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

      {/* Repository Configuration (root_dir + commands) */}
      {repo && (
        <div className="space-y-4 rounded-xl border border-white/8 bg-white/[0.02] p-5" data-testid="repo-config">
          <div>
            <p className="text-xs font-medium text-white/60 uppercase tracking-wider">
              Repository Configuration
            </p>
            <p className="mt-1 text-xs text-white/35">
              Set the project directory for monorepos. Changes reset the setup
              failure counter and unpause the repo.
            </p>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-white/50 mb-1">
                Project directory
                <span className="ml-1.5 text-white/25">(optional)</span>
              </label>
              <input
                type="text"
                value={rootDir}
                onChange={(e) => { setRootDir(e.target.value); setConfigSaved(false); }}
                placeholder="e.g. apps/web, packages/backend"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
              />
              <p className="mt-1 text-xs text-white/30">
                Leave blank to use the repository root.
              </p>
            </div>

            <div>
              <label className="block text-xs text-white/50 mb-1">Install command</label>
              <input
                type="text"
                value={installCmd}
                onChange={(e) => { setInstallCmd(e.target.value); setConfigSaved(false); }}
                placeholder="e.g. npm ci, pnpm install --frozen-lockfile"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs text-white/50 mb-1">Build command</label>
              <input
                type="text"
                value={buildCmd}
                onChange={(e) => { setBuildCmd(e.target.value); setConfigSaved(false); }}
                placeholder="e.g. npm run build"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs text-white/50 mb-1">Test command</label>
              <input
                type="text"
                value={testCmd}
                onChange={(e) => { setTestCmd(e.target.value); setConfigSaved(false); }}
                placeholder="e.g. npm test, pytest"
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-mono text-white placeholder-white/20 focus:border-white/25 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={handleSaveConfig}
              disabled={isConfigPending}
              className="rounded-full border border-white/15 bg-white/10 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-white/15 disabled:opacity-50"
            >
              {isConfigPending ? "Saving…" : "Save configuration"}
            </button>
            {configSaved && (
              <span className="text-sm text-emerald-400">Configuration saved.</span>
            )}
            {configError && (
              <span className="text-sm text-red-400">{configError}</span>
            )}
          </div>
        </div>
      )}

      {/* Max PRs per day */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Max PRs per day
        </label>
        <input
          type="number"
          min={1}
          max={50}
          value={settings.max_prs_per_day}
          onChange={(e) => handleChange("max_prs_per_day", parseInt(e.target.value, 10) || 1)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
        <p className="text-xs text-white/35">
          The agent stops opening new PRs once this limit is reached in a 24-hour window.
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

      {/* Execution strategy mode */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Baseline execution mode
        </label>
        <select
          value={settings.execution_mode}
          onChange={(e) => handleChange("execution_mode", e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white focus:border-white/25 focus:outline-none"
        >
          <option value="adaptive" className="bg-neutral-900">Adaptive (recommended)</option>
          <option value="strict" className="bg-neutral-900">Strict</option>
        </select>
        <p className="text-xs text-white/35">
          Adaptive runs strict first, then applies one bounded fallback strategy when
          failures match known signatures.
        </p>
      </div>

      {/* Max strategy attempts */}
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-white/60 uppercase tracking-wider">
          Max baseline strategy attempts
        </label>
        <input
          type="number"
          min={1}
          max={3}
          value={settings.max_strategy_attempts}
          onChange={(e) => handleChange("max_strategy_attempts", parseInt(e.target.value, 10) || 1)}
          className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none focus:ring-0"
        />
        <p className="text-xs text-white/35">
          Hard cap for strict + adaptive retries (1-3).
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
                    setSaved(false);
                    setError(null);
                    setSettings((prev) => ({
                      ...prev,
                      llm_provider: p.id,
                      llm_model: p.models[0]?.id ?? "",
                    }));
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
