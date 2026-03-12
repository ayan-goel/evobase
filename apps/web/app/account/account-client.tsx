"use client";

import { useState } from "react";
import Image from "next/image";
import { PlanBadge } from "@/components/billing/plan-badge";
import { UsageMeter } from "@/components/billing/usage-meter";
import { PlanSelector } from "@/components/billing/plan-selector";
import { PaymentForm } from "@/components/billing/payment-form";
import { cancelPlan, upgradePlan, updateSpendLimit } from "@/lib/api";
import type { BillingSubscription, BillingUsage } from "@/lib/api-server";
import { createClient } from "@/lib/supabase/client";

interface AccountClientProps {
  email: string;
  avatarUrl: string | null;
  githubLogin: string | null;
  subscription: BillingSubscription | null;
  usage: BillingUsage | null;
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6">
      <h2 className="mb-4 text-sm font-semibold text-white/80 uppercase tracking-wider">
        {title}
      </h2>
      {children}
    </div>
  );
}

export function AccountClient({
  email,
  avatarUrl,
  githubLogin,
  subscription,
  usage,
}: AccountClientProps) {
  const [selectedTier, setSelectedTier] = useState<string | null>(null);
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [spendLimitInput, setSpendLimitInput] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const tier = subscription?.tier ?? "free";
  const isPaid = tier !== "free";

  function handleSelectTier(newTier: string) {
    if (newTier === tier) return;
    setSelectedTier(newTier);
    setActionError(null);
    setActionSuccess(null);
  }

  async function handleDirectUpgrade() {
    if (!selectedTier) return;
    setIsUpgrading(true);
    setActionError(null);
    try {
      await upgradePlan(selectedTier);
      setActionSuccess(`Plan upgraded to ${selectedTier}.`);
      setSelectedTier(null);
      // Reload page to get fresh server-side data
      window.location.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Upgrade failed");
    } finally {
      setIsUpgrading(false);
    }
  }

  async function handleCancel() {
    setIsCancelling(true);
    setActionError(null);
    try {
      await cancelPlan();
      setActionSuccess("Subscription cancelled. You'll remain on the current plan until period end.");
      window.location.reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Cancellation failed");
    } finally {
      setIsCancelling(false);
    }
  }

  async function handleSpendLimit() {
    const microdollars = spendLimitInput ? Math.round(parseFloat(spendLimitInput) * 1_000_000) : null;
    setActionError(null);
    try {
      await updateSpendLimit(microdollars);
      setActionSuccess(microdollars ? `Spend limit set to $${spendLimitInput}/month.` : "Spend limit removed.");
      setSpendLimitInput("");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to update spend limit");
    }
  }

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/";
  }

  const showPaymentForm = selectedTier && selectedTier !== "free" && !isPaid;
  const showDirectUpgrade = selectedTier && selectedTier !== "free" && isPaid;

  return (
    <div className="space-y-6">
      {/* Profile */}
      <SectionCard title="Profile">
        <div className="flex items-center gap-4">
          {avatarUrl ? (
            <Image
              src={avatarUrl}
              alt={githubLogin ?? "Avatar"}
              width={48}
              height={48}
              className="rounded-full"
            />
          ) : (
            <div className="h-12 w-12 rounded-full bg-white/10 flex items-center justify-center text-white/50 text-lg font-semibold">
              {email.charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-sm font-medium text-white">{githubLogin ?? "—"}</p>
            <p className="text-xs text-white/50">{email}</p>
          </div>
        </div>
      </SectionCard>

      {/* Plan & Usage */}
      <SectionCard title="Plan & Usage">
        <div className="flex items-center justify-between mb-4">
          <PlanBadge tier={tier} />
          {subscription?.status === "past_due" && (
            <span className="rounded-full bg-red-500/10 border border-red-500/20 px-2.5 py-0.5 text-xs text-red-400">
              Past due
            </span>
          )}
        </div>

        {subscription && (
          <UsageMeter
            usagePct={subscription.usage_pct}
            periodEnd={subscription.current_period_end}
            overageActive={subscription.overage_active}
            className="mb-4"
          />
        )}

        {subscription?.overage_active && isPaid && (
          <div className="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-400">
            You&apos;re in pay-as-you-go mode. Runs are being charged at the overage rate.
          </div>
        )}

        {/* Spend limit for paid overage plans */}
        {isPaid && (
          <div className="mt-4">
            <p className="text-xs text-white/50 mb-2">
              Monthly spend cap (overage):{" "}
              {subscription?.monthly_spend_limit_microdollars
                ? `$${(subscription.monthly_spend_limit_microdollars / 1_000_000).toFixed(2)}/month`
                : "None (unlimited)"}
            </p>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="e.g. 50"
                value={spendLimitInput}
                onChange={(e) => setSpendLimitInput(e.target.value)}
                className="w-32 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/20"
              />
              <button
                type="button"
                onClick={handleSpendLimit}
                className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/[0.04] transition-colors"
              >
                Set limit
              </button>
              {subscription?.monthly_spend_limit_microdollars && (
                <button
                  type="button"
                  onClick={() => { setSpendLimitInput(""); updateSpendLimit(null); }}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/40 hover:bg-white/[0.04] transition-colors"
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        )}
      </SectionCard>

      {/* Billing */}
      <SectionCard title="Billing">
        <p className="mb-4 text-sm text-white/50">
          Change your plan. Upgrades take effect immediately.
        </p>

        <PlanSelector
          currentTier={tier}
          onSelect={handleSelectTier}
          disabled={isUpgrading}
        />

        {/* Payment form for new subscribers */}
        {showPaymentForm && selectedTier && (
          <div className="mt-4">
            <PaymentForm
              selectedTier={selectedTier}
              onSuccess={() => { setSelectedTier(null); setActionSuccess("Plan upgraded!"); window.location.reload(); }}
              onCancel={() => setSelectedTier(null)}
            />
          </div>
        )}

        {/* Direct upgrade for existing Stripe subscribers */}
        {showDirectUpgrade && selectedTier && (
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={handleDirectUpgrade}
              disabled={isUpgrading}
              className="rounded-lg bg-white px-5 py-2 text-sm font-semibold text-black hover:bg-white/90 disabled:opacity-50 transition-colors"
            >
              {isUpgrading ? "Upgrading…" : `Upgrade to ${selectedTier}`}
            </button>
            <button
              type="button"
              onClick={() => setSelectedTier(null)}
              className="rounded-lg border border-white/10 px-5 py-2 text-sm text-white/70 hover:bg-white/[0.04] transition-colors"
            >
              Cancel
            </button>
          </div>
        )}

        {actionError && (
          <p className="mt-3 text-xs text-red-400">{actionError}</p>
        )}
        {actionSuccess && (
          <p className="mt-3 text-xs text-emerald-400">{actionSuccess}</p>
        )}

        {isPaid && subscription?.status !== "canceled" && (
          <div className="mt-6 border-t border-white/[0.06] pt-4">
            <button
              type="button"
              onClick={handleCancel}
              disabled={isCancelling}
              className="text-xs text-white/30 hover:text-white/60 transition-colors"
            >
              {isCancelling ? "Cancelling…" : "Cancel subscription"}
            </button>
          </div>
        )}
      </SectionCard>

      {/* Usage breakdown */}
      {usage && usage.runs.length > 0 && (
        <SectionCard title="Recent Usage">
          <div className="space-y-2">
            {usage.runs.slice(0, 5).map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between text-sm"
              >
                <span className="font-mono text-xs text-white/40">
                  {run.run_id.slice(0, 8)}…
                </span>
                <span className="text-xs text-white/50">
                  {new Date(run.created_at).toLocaleDateString()}
                </span>
                <span className="text-xs text-white/60">
                  {run.call_count} LLM calls
                </span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Danger Zone */}
      <SectionCard title="Danger Zone">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-white/70">Sign out of your account</p>
            <p className="text-xs text-white/40">You can sign back in at any time.</p>
          </div>
          <button
            type="button"
            onClick={handleSignOut}
            className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20"
          >
            Sign out
          </button>
        </div>
      </SectionCard>
    </div>
  );
}
